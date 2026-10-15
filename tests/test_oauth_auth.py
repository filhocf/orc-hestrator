"""RED tests for OAuth2 feature (resource-server, opaque token).

These tests MUST FAIL until the G4 implementation is complete.
Tests cover the auth.py module and OAuth2 integration with FastMCP.
"""

import asyncio
import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from task_orchestrator.server import mcp


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
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
        # Clear any existing env var
        monkeypatch.delenv("MCP_OAUTH_ENABLED", raising=False)
        monkeypatch.delenv("MCP_OAUTH_TOKENS", raising=False)
        
        verifier, auth_settings = build_auth()
        assert verifier is None
        assert auth_settings is None

    def test_build_auth_oauth_disabled_false(self, monkeypatch):
        """build_auth() with MCP_OAUTH_ENABLED='false' should return (None, None)."""
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
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
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
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
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:mysecret123,tpol:anothersecret")
        
        verifier = OpaqueTokenVerifier()
        
        result = asyncio.run(verifier.verify_token("unknown_token"))
        assert result is None

    def test_verify_empty_token(self, monkeypatch):
        """verify_token() with empty token should return None."""
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:mysecret123")
        
        verifier = OpaqueTokenVerifier()
        
        result = asyncio.run(verifier.verify_token(""))
        assert result is None

    def test_verify_token_from_different_persona(self, monkeypatch):
        """verify_token() should return AccessToken with correct persona for each valid token."""
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
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
        OpaqueTokenVerifier, build_auth = _get_auth_classes()
        
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
        
        # This will fail until auth wiring is implemented in server.py
        # The test expects that build_auth() is called and (None, None) is passed to FastMCP
        app = mcp.streamable_http_app()
        client = TestClient(app)
        
        # GET /mcp without Bearer should work (or at least not fail with 401)
        # Note: actual MCP protocol might require specific content, but auth-wise should pass
        response = client.get("/mcp")
        assert response.status_code != 401  # Should not be auth-rejected

    def test_health_endpoint_always_public(self, monkeypatch):
        """/health should respond 200 without Bearer in both OAuth states."""
        app = mcp.streamable_http_app()
        client = TestClient(app)
        
        # Test with OAuth disabled
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "false")
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Test with OAuth enabled (would require auth.py implementation)
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")
        
        # Recreate app with new env - this will fail until server.py reads build_auth()
        app = mcp.streamable_http_app() 
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 200

    def test_oauth_enabled_mcp_requires_bearer(self, monkeypatch):
        """With MCP_OAUTH_ENABLED=true, /mcp without Bearer should return 401."""
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")
        
        # This will fail until auth.py exists and server.py uses build_auth()
        app = mcp.streamable_http_app()
        client = TestClient(app)
        
        # Request without Bearer should be rejected
        response = client.get("/mcp")
        assert response.status_code == 401

    def test_oauth_enabled_mcp_accepts_valid_bearer(self, monkeypatch):
        """With MCP_OAUTH_ENABLED=true, /mcp with valid Bearer should not return 401."""
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
        monkeypatch.setenv("MCP_OAUTH_TOKENS", "zero:secret123")
        
        # This will fail until full implementation
        app = mcp.streamable_http_app()
        client = TestClient(app)
        
        # Request with valid Bearer should not be auth-rejected
        headers = {"Authorization": "Bearer secret123"}
        response = client.get("/mcp", headers=headers)
        assert response.status_code != 401  # Should pass auth (might fail for other reasons)


# Additional integration tests that might be fragile - marked as expected to be limited

@pytest.mark.xfail(reason="Integration test may be unstable until full stateless_http setup works")
def test_bearer_basic_coexistence():
    """Smoke test: basic in URL (nginx sim) + Bearer header should not collide."""
    # This test might be hard to implement stably until we understand
    # exactly how the nginx/FastMCP interaction works
    # Mark as xfail but document the requirement
    pass