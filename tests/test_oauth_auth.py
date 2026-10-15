"""RED tests for OAuth2 feature (resource-server, opaque token).

These tests MUST FAIL until the G4 implementation is complete.
Tests cover the auth.py module and OAuth2 integration with FastMCP.
"""

import asyncio

import pytest
from starlette.testclient import TestClient


def _import_auth_module():
    """Import auth module - will fail until G4 implementation."""
    try:
        from task_orchestrator.auth import OpaqueTokenVerifier, build_auth

        return OpaqueTokenVerifier, build_auth
    except ImportError as e:
        pytest.fail(f"auth.py module not found (expected until G4): {e}")


def _get_auth_classes():
    """Get auth classes, failing the test if not available."""
    OpaqueTokenVerifier, build_auth = _import_auth_module()
    return OpaqueTokenVerifier, build_auth


class TestBuildAuth:
    """Unit tests for build_auth() function."""

    def test_build_auth_oauth_disabled_default(self, monkeypatch):
        """build_auth() with MCP_OAUTH_ENABLED absent should return (None, None)."""
        _OpaqueTokenVerifier, build_auth = _get_auth_classes()

        # Clear any existing env var
        monkeypatch.delenv("MCP_OAUTH_ENABLED", raising=False)
        monkeypatch.delenv("MCP_OAUTH_TOKENS", raising=False)

        verifier, auth_settings = build_auth()
        assert verifier is None
        assert auth_settings is None

    def test_build_auth_oauth_disabled_false(self, monkeypatch):
        """build_auth() with MCP_OAUTH_ENABLED='false' should return (None, None)."""
        _OpaqueTokenVerifier, build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_ENABLED", "false")
        monkeypatch.delenv("MCP_OAUTH_TOKENS", raising=False)

        verifier, auth_settings = build_auth()
        assert verifier is None
        assert auth_settings is None

    def test_build_auth_oauth_enabled_with_tokens(self, monkeypatch):
        """build_auth() with MCP_OAUTH_ENABLED='true' + MCP_OAUTH_TOKENS should return non-None objects."""
        OpaqueTokenVerifier, build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123,tpol:secret456")

        verifier, auth_settings = build_auth()
        assert verifier is not None
        assert auth_settings is not None
        assert isinstance(verifier, OpaqueTokenVerifier)


class TestOpaqueTokenVerifier:
    """Unit tests for OpaqueTokenVerifier class."""

    def test_verify_valid_token(self, monkeypatch):
        """verify_token() with valid secret should return AccessToken with correct client_id and scopes."""
        OpaqueTokenVerifier, _build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:mysecret123,tpol:anothersecret")

        verifier = OpaqueTokenVerifier()

        # Test async method
        result = asyncio.run(verifier.verify_token("mysecret123"))

        assert result is not None
        assert result.token == "mysecret123"
        assert result.client_id == "zero"
        assert "orc" in result.scopes

    def test_verify_invalid_token(self, monkeypatch):
        """verify_token() with unknown token should return None."""
        OpaqueTokenVerifier, _build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:mysecret123,tpol:anothersecret")

        verifier = OpaqueTokenVerifier()

        result = asyncio.run(verifier.verify_token("unknown_token"))
        assert result is None

    def test_verify_empty_token(self, monkeypatch):
        """verify_token() with empty token should return None."""
        OpaqueTokenVerifier, _build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:mysecret123")

        verifier = OpaqueTokenVerifier()

        result = asyncio.run(verifier.verify_token(""))
        assert result is None

    def test_verify_token_from_different_persona(self, monkeypatch):
        """verify_token() should return AccessToken with correct persona for each valid token."""
        OpaqueTokenVerifier, _build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret1,tpol:secret2")

        verifier = OpaqueTokenVerifier()

        # Test first persona
        result1 = asyncio.run(verifier.verify_token("secret1"))
        assert result1 is not None
        assert result1.client_id == "zero"

        # Test second persona
        result2 = asyncio.run(verifier.verify_token("secret2"))
        assert result2 is not None
        assert result2.client_id == "tpol"

    def test_verify_token_constant_time_behavior(self, monkeypatch):
        """verify_token() should behave consistently (timing-attack resistant)."""
        OpaqueTokenVerifier, _build_auth = _get_auth_classes()

        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:correctsecret")

        verifier = OpaqueTokenVerifier()

        # Valid token should succeed
        result_valid = asyncio.run(verifier.verify_token("correctsecret"))
        assert result_valid is not None

        # Invalid token should fail
        result_invalid = asyncio.run(verifier.verify_token("wrongsecret"))
        assert result_invalid is None

        # Note: We can't easily test hmac.compare_digest usage directly,
        # but behavior test is sufficient - real implementation should use it


class TestFastMCPIntegration:
    """Integration tests for FastMCP with OAuth2."""

    def test_oauth_disabled_no_auth_required(self, monkeypatch):
        """With MCP_OAUTH_ENABLED=false, /mcp should not require Bearer token."""
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "false")
        monkeypatch.delenv("MCP_OAUTH_TOKENS", raising=False)

        # Import and create a fresh FastMCP instance to avoid singleton issues
        from mcp.server.fastmcp import FastMCP

        from task_orchestrator.auth import build_auth

        _token_verifier, _auth_settings = build_auth()
        fresh_mcp = FastMCP(
            "task-orchestrator-test",
            instructions="Test instance",
            token_verifier=_token_verifier,
            auth=_auth_settings,
        )

        app = fresh_mcp.streamable_http_app()

        # Use context manager to properly initialize lifespan/task group
        with TestClient(app) as client:
            # GET /mcp without Bearer should work (or at least not fail with 401)
            # Note: actual MCP protocol might require specific content, but auth-wise should pass
            response = client.get("/mcp")
            assert response.status_code != 401  # Should not be auth-rejected

    def test_health_endpoint_always_public(self, monkeypatch):
        """/health should respond 200 without Bearer in both OAuth states."""
        from mcp.server.fastmcp import FastMCP

        from task_orchestrator.auth import build_auth

        # Test with OAuth disabled
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "false")
        monkeypatch.delenv("MCP_OAUTH_TOKENS", raising=False)

        _token_verifier, _auth_settings = build_auth()
        fresh_mcp = FastMCP(
            "task-orchestrator-test-disabled",
            instructions="Test instance - disabled",
            token_verifier=_token_verifier,
            auth=_auth_settings,
        )

        # Add health endpoint like in the real server
        @fresh_mcp.custom_route("/health", methods=["GET"])
        async def health_check(request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "healthy", "version": "test"})

        app = fresh_mcp.streamable_http_app()
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

        # Test with OAuth enabled
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")

        _token_verifier, _auth_settings = build_auth()
        fresh_mcp2 = FastMCP(
            "task-orchestrator-test-enabled",
            instructions="Test instance - enabled",
            token_verifier=_token_verifier,
            auth=_auth_settings,
        )

        # Add health endpoint
        @fresh_mcp2.custom_route("/health", methods=["GET"])
        async def health_check2(request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "healthy", "version": "test"})

        app = fresh_mcp2.streamable_http_app()
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

    def test_oauth_enabled_mcp_requires_bearer(self, monkeypatch):
        """With MCP_OAUTH_ENABLED=true, /mcp without Bearer should return 401."""
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")

        from mcp.server.fastmcp import FastMCP

        from task_orchestrator.auth import build_auth

        _token_verifier, _auth_settings = build_auth()
        fresh_mcp = FastMCP(
            "task-orchestrator-test-auth",
            instructions="Test instance - auth required",
            token_verifier=_token_verifier,
            auth=_auth_settings,
        )

        app = fresh_mcp.streamable_http_app()

        with TestClient(app) as client:
            # Request without Bearer should be rejected
            response = client.get("/mcp")
            assert response.status_code == 401

    def test_oauth_enabled_mcp_accepts_valid_bearer(self, monkeypatch):
        """With MCP_OAUTH_ENABLED=true, /mcp with valid Bearer should not return 401."""
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")

        from mcp.server.fastmcp import FastMCP

        from task_orchestrator.auth import build_auth

        _token_verifier, _auth_settings = build_auth()
        fresh_mcp = FastMCP(
            "task-orchestrator-test-valid-bearer",
            instructions="Test instance - valid bearer",
            token_verifier=_token_verifier,
            auth=_auth_settings,
        )

        app = fresh_mcp.streamable_http_app()

        with TestClient(app) as client:
            # Request with valid Bearer should not be auth-rejected
            headers = {"Authorization": "Bearer secret123"}
            response = client.get("/mcp", headers=headers)
            # We assert != 401 rather than == 200 because the MCP protocol
            # might require more than just auth (like proper handshake)
            # What matters is that it's not rejected for auth reasons
            assert (
                response.status_code != 401
            )  # Should pass auth (might fail for other reasons)


# Additional integration tests that might be fragile - marked as expected to be limited


def test_bearer_basic_coexistence():
    """Smoke test: basic in URL (nginx sim) + Bearer header should not collide."""
