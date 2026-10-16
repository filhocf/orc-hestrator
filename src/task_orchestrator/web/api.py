"""REST API over the engine for the decoupled management UI (Orc 1.5.0 backend half).

Thin layer: every endpoint is ONE engine call, result returned as JSON. No business logic.
Mounted at /api on the FastMCP streamable_http_app() by server.main() (R1/R11/R12).

- ToolError.code -> HTTP status (R4); generic exception -> 500 INTERNAL, no stacktrace (R5).
- CORS from MCP_UI_CORS_ORIGINS, dev default http://localhost:5173 (R6).
- Writes resolve the human actor and set the agent_id contextvar for the request scope,
  resetting it in finally, so created_by/updated_by reflect the UI user (R7).
- get_current_user: single identity/authz extension point (v1 stub -> actor string) (R10).
"""

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from .. import engine
from ..engine import ToolError
from ..engine.base import reset_agent_id, set_agent_id
from .graph import build_cytoscape_data

logger = logging.getLogger(__name__)

# Session cookie name (SPEC §Architecture: HTTP-only opaque token).
_SESSION_COOKIE = "orc_session"

# Paths reachable WITHOUT a session (R9). Everything else under /api/* is protected.
# logout is public so it stays idempotent (always 204) even without a valid session (R6).
_PUBLIC_PATHS = frozenset({"/api/auth/login", "/api/auth/logout", "/health"})

# Collection pagination bounds, clamped at the HTTP edge so a hostile
# ?limit=999999 / ?limit=-1 can never materialize the whole table. The engine
# keeps its own permissive contract (MCP compat) — the clamp lives here only.
_MAX_LIMIT = 200
_MIN_LIMIT = 1


def _clamp_limit(limit: int) -> int:
    """Clamp a collection limit into [1, 200] (DoS guard at the HTTP edge)."""
    return max(_MIN_LIMIT, min(limit, _MAX_LIMIT))


def _clamp_offset(offset: int) -> int:
    """Floor a collection offset at 0 (negative offset is meaningless)."""
    return max(0, offset)


# ToolError.code -> HTTP status (SPEC R4 / G0 §4).
_CODE_TO_STATUS = {
    "NOT_FOUND": 404,
    "VALIDATION": 400,
    "CONFLICT": 409,
    "DEPENDENCY_UNSATISFIED": 422,
    "GATE_BLOCKED": 422,
}


# Whitelist of user fields the REST layer is allowed to expose (F3 / R10).
# password_hash is NEVER in this set, so a hash can never leak through /api/users.
_USER_PUBLIC_FIELDS = (
    "id",
    "username",
    "role",
    "active",
    "created_at",
    "last_login_at",
)


def _serialize_user(user: dict) -> dict:
    """Project a user dict onto the public whitelist (drops any hash/secret)."""
    return {k: user.get(k) for k in _USER_PUBLIC_FIELDS}


def _cors_origins() -> list[str]:
    """Read allowed origins from MCP_UI_CORS_ORIGINS (comma-separated), dev default Vite.

    The REST app sets allow_credentials=True, and the CORS spec forbids the
    '*' wildcard together with credentials (browsers reject it and it is a
    security footgun). Drop any '*' and warn, keeping the explicit origins.
    """
    raw = os.environ.get("MCP_UI_CORS_ORIGINS", "http://localhost:5173")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        logger.warning(
            "MCP_UI_CORS_ORIGINS contained '*', which is forbidden with "
            "allow_credentials=True; dropping the wildcard and keeping the "
            "explicit origins."
        )
        origins = [o for o in origins if o != "*"]
    return origins


def _resolve_session_user(request: Request) -> dict | None:
    """Resolve the session cookie to a public user dict, or None if no valid session."""
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return engine.lookup_session(token)


def get_current_user(request: Request) -> str:
    """Resolve the human actor from the session cookie (R8, the R10 extension point).

    Valid session -> "user:<username>". No/invalid/expired session -> 401 on the
    protected route. The dependency signature of existing routes does NOT change.
    """
    user = _resolve_session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return f"user:{user['username']}"


def require_admin(request: Request) -> str:
    """RBAC dependency: 401 if no session, 403 if the session user is not an admin (R10)."""
    user = _resolve_session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return f"user:{user['username']}"


class _SessionAuthMiddleware(BaseHTTPMiddleware):
    """Enforce R9: every /api/* route requires a session except the public allowlist."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)
        # CORS preflight must pass through (no cookies on OPTIONS).
        if request.method == "OPTIONS":
            return await call_next(request)
        if _resolve_session_user(request) is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHENTICATED",
                        "message": "Authentication required",
                    }
                },
            )
        return await call_next(request)


def build_rest_app() -> FastAPI:
    """Build the REST sub-app: routes under /api, CORS, ToolError->HTTP handlers (R1)."""
    app = FastAPI(title="Orc REST API", docs_url="/docs", openapi_url="/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # R9: enforce a valid session on every /api/* route except the public allowlist.
    app.add_middleware(_SessionAuthMiddleware)

    @app.get("/health")
    def health() -> dict:
        """Public liveness probe (R9: reachable without a session)."""
        return {"status": "ok"}

    @app.exception_handler(ToolError)
    async def _tool_error_handler(_request: Request, exc: ToolError) -> JSONResponse:
        status = _CODE_TO_STATUS.get(exc.code, 400)
        return JSONResponse(status_code=status, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def _generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        # R5: never leak a stacktrace to the client.
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL", "message": "Internal server error"}},
        )

    router = APIRouter(prefix="/api")

    # ---- AUTH (public: login; session: logout, me) --------------------------
    def _is_secure_request(request: Request) -> bool:
        """Decide whether the session cookie must carry the Secure flag.

        Behind nginx (TLS terminated at the proxy) the request reaches us over
        plain http, so request.url.scheme is 'http' and the hostname may be
        internal/empty — we must NOT treat that as insecure in production or the
        prod orc_session cookie ships without Secure. Honor, in order:

          1. ORC_COOKIE_SECURE=1 — explicit operator override (always Secure).
          2. X-Forwarded-Proto: https — set by the TLS-terminating proxy.
          3. request.url.scheme == 'https' — direct TLS (no proxy).

        Local dev over plain http (localhost/127.0.0.1/::1/testserver) matches none
        of these, so the cookie stays non-Secure and TestClient/dev flows work.
        """
        if os.environ.get("ORC_COOKIE_SECURE") == "1":
            return True
        forwarded_proto = (
            request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        )
        if forwarded_proto == "https":
            return True
        return request.url.scheme == "https"

    @router.post("/auth/login")
    def auth_login(body: dict, request: Request, response: Response) -> dict:
        body = body or {}
        username = body.get("username", "")
        password = body.get("password", "")
        user = engine.verify_credentials(username, password)
        if user is None:
            # R4: generic 401, identical for unknown user / wrong password / inactive.
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = engine.create_session(user["username"])
        engine.touch_last_login(user["username"])
        response.set_cookie(
            key=_SESSION_COOKIE,
            value=token,
            httponly=True,
            samesite="lax",
            secure=_is_secure_request(request),
            path="/",
        )
        return {"user": {"username": user["username"], "role": user["role"]}}

    @router.post("/auth/logout", status_code=204)
    def auth_logout(request: Request, response: Response) -> Response:
        token = request.cookies.get(_SESSION_COOKIE)
        if token:
            engine.delete_session(token)  # idempotent
        response.delete_cookie(key=_SESSION_COOKIE, path="/")
        response.status_code = 204
        return response

    @router.get("/auth/me")
    def auth_me(request: Request) -> dict:
        user = _resolve_session_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"user": {"username": user["username"], "role": user["role"]}}

    # ---- USERS (admin-only management, F3 / R10) ----------------------------
    @router.get("/users")
    def list_users(_admin: str = Depends(require_admin)) -> dict:
        """List all users (admin-only). Serialized through the public whitelist so
        password_hash can NEVER leak."""
        return {"users": [_serialize_user(u) for u in engine.list_users()]}

    @router.post("/users", status_code=201)
    def create_user(body: dict, actor: str = Depends(require_admin)) -> dict:
        """Create a user (admin-only). role must be in {admin, user}; duplicate
        username -> ToolError CONFLICT -> 409. The response never echoes the secret.
        """
        body = body or {}
        username = body.get("username", "")
        password = body.get("password", "")
        role = body.get("role", "user")
        if role not in {"admin", "user"}:
            raise ToolError("VALIDATION", f"Invalid role: {role}", "role")
        # engine.create_user validates fields, hashes the password, and raises
        # ToolError CONFLICT on a duplicate username (COLLATE NOCASE); it returns
        # the public dict (no hash). created_by records the acting admin (R7).
        token = set_agent_id(actor)
        try:
            created = engine.create_user(
                username=username,
                password=password,
                role=role,
                created_by=actor,
            )
        finally:
            reset_agent_id(token)
        return {"user": _serialize_user(created)}

    # ---- READS (each = one engine call) -------------------------------------
    @router.get("/items")
    def list_items(
        status: str | None = None,
        tags: str | None = None,
        parent_id: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        limit = _clamp_limit(limit)
        offset = _clamp_offset(offset)
        items = engine.query_items(
            status=status,
            parent_id=parent_id,
            priority=priority,
            search=search,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    @router.get("/items/{item_id}")
    def item_detail(item_id: str) -> dict:
        # get_context(item_id) raises ToolError NOT_FOUND if absent, and returns
        # {item, children, notes, blockers, ...}. Flatten item + attach deps + claim.
        ctx = engine.get_context(item_id)
        item = ctx["item"]
        result = dict(item)
        result["children"] = ctx.get("children", [])
        result["notes"] = ctx.get("notes", [])
        result["dependencies"] = engine.get_dependencies(item_id, "both")
        result["claim"] = engine.get_claim_for("work_item", item_id)
        return result

    @router.get("/arcs")
    def list_arcs(limit: int = 50, offset: int = 0) -> dict:
        limit = _clamp_limit(limit)
        offset = _clamp_offset(offset)
        items = engine.query_items(tags="arc", limit=limit, offset=offset)
        return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    @router.get("/arcs/{item_id}")
    def arc_tree(item_id: str) -> dict:
        return {"children": engine.get_children(item_id)}

    @router.get("/context")
    def context() -> dict:
        return engine.get_context()

    @router.get("/sessions")
    def sessions(
        hostname: str | None = None, agent_id: str | None = None
    ) -> list[dict]:
        return engine.presence_list(hostname=hostname, agent_id=agent_id)

    @router.get("/claims")
    def claims(subject: str | None = None) -> dict:
        # By subject ("work_item:ref" or a bare work_item id) -> the active claim.
        if subject:
            if ":" in subject:
                subject_type, subject_ref = subject.split(":", 1)
            else:
                subject_type, subject_ref = "work_item", subject
            return {"claim": engine.get_claim_for(subject_type, subject_ref)}
        return {"claim": None}

    @router.get("/metrics")
    def metrics(days: int = 30, workspace: str | None = None) -> dict:
        return engine.get_metrics(days=days, workspace=workspace)

    @router.get("/metrics/graph")
    def metrics_graph(workspace: str | None = None, root_id: str | None = None) -> dict:
        return engine.get_project_graph_metrics(workspace=workspace, root_id=root_id)

    @router.get("/graph/{arc_id}")
    def graph(arc_id: str) -> dict:
        children = engine.get_children(arc_id)
        return build_cytoscape_data(arc_id, children)

    @router.get("/workspaces")
    def workspaces() -> dict:
        from ..workspace import list_workspaces

        return list_workspaces()

    # ---- WRITES (resolve actor -> set agent_id contextvar -> reset in finally, R7) ----
    @router.patch("/items/{item_id}/advance")
    def advance(
        item_id: str, body: dict, actor: str = Depends(get_current_user)
    ) -> dict:
        trigger = (body or {}).get("trigger", "")
        token = set_agent_id(actor)
        try:
            return engine.advance_item(item_id, trigger)
        finally:
            reset_agent_id(token)

    @router.post("/claims")
    def claim(body: dict, actor: str = Depends(get_current_user)) -> dict:
        body = body or {}
        token = set_agent_id(actor)
        try:
            return engine.claim(
                subject_type=body.get("subject_type", ""),
                subject_ref=body.get("subject_ref", ""),
                session_id=body.get("session_id", ""),
            )
        finally:
            reset_agent_id(token)

    @router.delete("/claims")
    def release(body: dict, actor: str = Depends(get_current_user)) -> dict:
        body = body or {}
        token = set_agent_id(actor)
        try:
            removed = engine.release(
                session_id=body.get("session_id", ""),
                subject_type=body.get("subject_type", ""),
                subject_ref=body.get("subject_ref", ""),
            )
            return {"released": removed}
        finally:
            reset_agent_id(token)

    app.include_router(router)
    return app
