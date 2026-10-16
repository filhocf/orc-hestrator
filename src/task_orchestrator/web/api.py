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

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette.middleware.cors import CORSMiddleware

from .. import engine
from ..engine import ToolError
from ..engine.base import reset_agent_id, set_agent_id
from .graph import build_cytoscape_data

logger = logging.getLogger(__name__)

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


def get_current_user(request: Request) -> str:
    """Resolve the human actor for the request (R10 extension point).

    v1 stub: X-Forwarded-User (set by nginx) or the generic 'ui' fallback. In 1.5.0 this
    becomes user-session + RBAC validation WITHOUT changing any route signature.
    """
    forwarded = request.headers.get("x-forwarded-user")
    if forwarded and forwarded.strip():
        return f"user:{forwarded.strip()}"
    return "ui"


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
