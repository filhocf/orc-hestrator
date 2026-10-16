"""User authentication + RBAC sub-domain (F1, SPEC-user-auth-rbac).

Pure functions over get_connection(), mirroring engine/presence.py: explicit
commit()/close() in finally, helpers from .base.

Passwords are hashed with hashlib.scrypt (stdlib, memory-hard) using a per-user
random salt; the stored format is 'scrypt$n$r$p$salt_hex$hash_hex'. Verification is
constant-time (hmac.compare_digest). Plaintext passwords are NEVER stored or logged.

Sessions are server-side: the HTTP cookie carries an opaque random token (secrets),
and only its SHA-256 hash is persisted in user_sessions, so a DB leak cannot replay
cookies and logout/disable revoke immediately.
"""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

from ..db import get_connection
from .base import ToolError, _now, _row_to_dict, _uid

logger = logging.getLogger(__name__)

# scrypt cost parameters (RFC 7914). n must be a power of two; these are a sane
# interactive-auth default (n=2**14) for a small team on a small VPS.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16

VALID_ROLES = {"admin", "user"}


# --- password hashing -------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a plaintext password with scrypt + random salt.

    Returns 'scrypt$n$r$p$salt_hex$hash_hex'. Never logs the plaintext.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify a plaintext password against a stored scrypt string."""
    try:
        scheme, n_s, r_s, p_s, salt_hex, hash_hex = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if scheme != "scrypt":
        return False
    try:
        n, r, p = int(n_s), int(r_s), int(p_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=len(expected),
    )
    return hmac.compare_digest(dk, expected)


# Precomputed at import with the SAME scrypt cost params as a real user, over a
# random throwaway password. verify_credentials() runs a full scrypt verify against
# this on the unknown/inactive branch so that branch costs the same as a
# wrong-password attempt, closing the user-enumeration timing side-channel (R4).
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


# --- users ------------------------------------------------------------------
def _public_user(row) -> dict | None:
    """Row -> safe dict WITHOUT the password_hash (never leak the hash)."""
    d = _row_to_dict(row)
    if d is None:
        return None
    d.pop("password_hash", None)
    d["active"] = bool(d.get("active", 0))
    return d


def create_user(
    username: str,
    password: str,
    role: str = "user",
    created_by: str | None = None,
) -> dict:
    """Create a user. Returns the public dict (no hash). Raises on bad input/duplicate."""
    username = (username or "").strip()
    if not username:
        raise ToolError("VALIDATION", "username is required", "username")
    if not password:
        raise ToolError("VALIDATION", "password is required", "password")
    if role not in VALID_ROLES:
        raise ToolError(
            "VALIDATION", f"Invalid role: {role}. Valid: {sorted(VALID_ROLES)}", "role"
        )
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        if existing:
            raise ToolError("CONFLICT", f"User '{username}' already exists", "username")
        user_id = _uid()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, active, created_at, created_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, username, hash_password(password), role, 1, _now(), created_by),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _public_user(row)
    finally:
        conn.close()


def get_user(username: str) -> dict | None:
    """Return the FULL user row (INCLUDING password_hash) by username, or None.

    Used internally (verify, hash checks). HTTP layers must never echo the hash.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_users() -> list[dict]:
    """List all users as public dicts (no hashes), newest first."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [_public_user(r) for r in rows]
    finally:
        conn.close()


def set_user_active(username: str, active: bool) -> bool:
    """Enable/disable a user. Returns True if a row was updated."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE users SET active = ? WHERE username = ? COLLATE NOCASE",
            (1 if active else 0, username),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def verify_credentials(username: str, password: str) -> dict | None:
    """Verify credentials for an ACTIVE user. Returns the public user dict or None.

    Same None return for unknown user, wrong password, and inactive user — the HTTP
    layer turns all of these into an identical generic 401 (R4, no enumeration).

    To close a timing side-channel (R4), the unknown/inactive branch still runs a
    full scrypt verification against a module-level dummy hash (same cost params as
    a real user) before returning None, so an attacker cannot distinguish a missing
    username from a wrong password by measuring login latency.
    """
    row = get_user(username)
    if row is None or not row.get("active"):
        # Equalize cost: pay the same scrypt work as the wrong-password branch.
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return _public_user(row)


def touch_last_login(username: str) -> None:
    """Record the last successful login timestamp."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE username = ? COLLATE NOCASE",
            (_now(), username),
        )
        conn.commit()
    finally:
        conn.close()


# --- sessions ---------------------------------------------------------------
def _hash_token(token: str) -> str:
    """SHA-256 hex of the opaque session token (stored at rest, never the token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_ttl_hours() -> float:
    """Read ORC_SESSION_TTL_HOURS (default 168 = 7 days). 0 => already-expired."""
    raw = os.environ.get("ORC_SESSION_TTL_HOURS", "168")
    try:
        return float(raw)
    except ValueError:
        return 168.0


def create_session(username: str) -> str:
    """Create a server-side session for an existing user. Returns the OPAQUE token.

    The caller sets the token as the orc_session cookie; only token_hash is stored.
    """
    user = get_user(username)
    if user is None:
        raise ToolError("NOT_FOUND", f"User '{username}' not found", "username")
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(hours=_session_ttl_hours())).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO user_sessions (token_hash, user_id, expires_at, created_at) "
            "VALUES (?,?,?,?)",
            (_hash_token(token), user["id"], expires_at, _now()),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def lookup_session(token: str) -> dict | None:
    """Resolve an opaque token to its public user, or None if invalid/expired.

    Expired sessions are pruned lazily on access (R12).
    """
    if not token:
        return None
    token_hash = _hash_token(token)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if row is None:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except (ValueError, TypeError):
            expires = None
        if expires is None or expires <= datetime.now(UTC):
            # lazy prune of the expired row
            conn.execute(
                "DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,)
            )
            conn.commit()
            return None
        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (row["user_id"],)
        ).fetchone()
        user = _public_user(user_row)
        if user is None or not user.get("active"):
            return None
        return user
    finally:
        conn.close()


def delete_session(token: str) -> bool:
    """Revoke a session by its opaque token. Returns True if a row was removed."""
    if not token:
        return False
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM user_sessions WHERE token_hash = ?", (_hash_token(token),)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def prune_expired() -> int:
    """Delete all expired sessions. Returns the count removed."""
    now = datetime.now(UTC).isoformat()
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM user_sessions WHERE expires_at <= ?", (now,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- admin seed -------------------------------------------------------------
def seed_admin() -> dict | None:
    """Create the initial admin from ORC_ADMIN_USER/ORC_ADMIN_PASSWORD (R11).

    Idempotent: only acts when both env vars are set AND no admin exists. Absence of
    the env vars never crashes startup. Logs WITHOUT the password.
    """
    username = os.environ.get("ORC_ADMIN_USER", "").strip()
    password = os.environ.get("ORC_ADMIN_PASSWORD", "")
    if not username or not password:
        return None
    conn = get_connection()
    try:
        has_admin = conn.execute(
            "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if has_admin:
        return None
    user = create_user(
        username=username, password=password, role="admin", created_by="user:system"
    )
    logger.info("Seeded initial admin user '%s' from environment.", username)
    return user
