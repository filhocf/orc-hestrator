"""Test agent_id boundary resolution (R1, R5).

Tests the boundary layer that resolves X-Agent-ID headers to contextvar and ensures
mandatory reset to prevent leakage between requests.
"""

import os
from unittest.mock import Mock, patch

import pytest

from task_orchestrator.engine.base import get_agent_id, reset_agent_id, set_agent_id
from task_orchestrator.server import _resolve_agent_id, with_agent_id


class TestAgentIdResolution:
    """Test the _resolve_agent_id function with various precedence scenarios."""

    def test_resolve_agent_id_from_header(self):
        """R1: X-Agent-ID header takes precedence over env/oauth."""
        # Mock MCP context with request headers
        mock_request = Mock()
        mock_request.headers = {"x-agent-id": "header-agent"}

        mock_context = Mock()
        mock_context.request_context = Mock()
        mock_context.request_context.request = mock_request

        with (
            patch.dict(os.environ, {"MCP_AGENT_ID": "env-agent"}),
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            mock_mcp.get_context.return_value = mock_context

            result = _resolve_agent_id()
            assert result == "header-agent"

    def test_resolve_agent_id_from_env_when_no_header(self):
        """R1: MCP_AGENT_ID env var used when no header present."""
        # Mock MCP context with empty headers
        mock_request = Mock()
        mock_request.headers = {}

        mock_context = Mock()
        mock_context.request_context = Mock()
        mock_context.request_context.request = mock_request

        with (
            patch.dict(os.environ, {"MCP_AGENT_ID": "env-agent"}),
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            mock_mcp.get_context.return_value = mock_context

            result = _resolve_agent_id()
            assert result == "env-agent"

    def test_resolve_agent_id_from_oauth_when_no_header_or_env(self):
        """R1: OAuth client_id used as fallback when header and env are empty."""
        # Mock MCP context with empty headers
        mock_request = Mock()
        mock_request.headers = {}

        mock_context = Mock()
        mock_context.request_context = Mock()
        mock_context.request_context.request = mock_request

        # Mock OAuth access token via _current_access_token
        mock_token = Mock()
        mock_token.client_id = "oauth-client"

        with (
            patch.dict(os.environ, {}, clear=True),  # Clear MCP_AGENT_ID
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            mock_mcp.get_context.return_value = mock_context
            mock_mcp._current_access_token = mock_token

            # Mock token verifier to simulate OAuth being enabled
            with patch("task_orchestrator.server._token_verifier", True):
                result = _resolve_agent_id()
                assert result == "oauth-client"

    def test_resolve_agent_id_returns_none_when_all_empty(self):
        """R4: Returns None when no agent_id can be resolved."""
        # Mock MCP context with empty headers
        mock_request = Mock()
        mock_request.headers = {}

        mock_context = Mock()
        mock_context.request_context = Mock()
        mock_context.request_context.request = mock_request

        with (
            patch.dict(os.environ, {}, clear=True),  # Clear MCP_AGENT_ID
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            mock_mcp.get_context.return_value = mock_context
            # No _current_access_token attribute (OAuth not available)

            with patch("task_orchestrator.server._token_verifier", None):
                result = _resolve_agent_id()
                assert result is None

    def test_resolve_agent_id_handles_no_request_context(self):
        """Handles non-HTTP contexts gracefully by falling back to env/oauth/None."""
        with (
            patch.dict(os.environ, {"MCP_AGENT_ID": "env-fallback"}),
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            # Simulate no request context (non-HTTP invocation)
            mock_mcp.get_context.side_effect = Exception("No context")

            result = _resolve_agent_id()
            assert result == "env-fallback"

    def test_resolve_agent_id_normalizes_whitespace_to_none(self):
        """R10: Empty/whitespace strings are treated as absent."""
        # Test header with whitespace
        mock_request = Mock()
        mock_request.headers = {"x-agent-id": "   "}

        mock_context = Mock()
        mock_context.request_context = Mock()
        mock_context.request_context.request = mock_request

        with (
            patch.dict(os.environ, {"MCP_AGENT_ID": "env-agent"}),
            patch("task_orchestrator.server.mcp") as mock_mcp,
        ):
            mock_mcp.get_context.return_value = mock_context

            result = _resolve_agent_id()
            # Should fall through to env because header is whitespace
            assert result == "env-agent"


class TestWithAgentIdDecorator:
    """Test the @with_agent_id decorator ensures set/reset behavior (R5)."""

    def test_with_agent_id_sets_and_resets_contextvar(self):
        """R5: Decorator sets agent_id at start and resets at end."""
        # Set initial state
        initial_token = set_agent_id("initial-agent")

        @with_agent_id
        def dummy_tool():
            # Inside tool, should have resolved agent_id
            return get_agent_id()

        try:
            with patch("task_orchestrator.server._resolve_agent_id") as mock_resolve:
                mock_resolve.return_value = "resolved-agent"

                # Call decorated function
                result = dummy_tool()

                # Should have returned the resolved agent_id from inside the tool
                assert result == "resolved-agent"

                # After tool execution, should be back to initial state
                assert get_agent_id() == "initial-agent"
        finally:
            # Cleanup
            reset_agent_id(initial_token)

    def test_with_agent_id_resets_even_on_exception(self):
        """R5: Decorator resets agent_id even if tool raises exception."""
        # Set initial state
        initial_token = set_agent_id("initial-agent")

        @with_agent_id
        def failing_tool():
            assert get_agent_id() == "resolved-agent"  # Verify it was set
            raise ValueError("Tool failed")

        try:
            with patch("task_orchestrator.server._resolve_agent_id") as mock_resolve:
                mock_resolve.return_value = "resolved-agent"

                # Call decorated function that raises exception
                with pytest.raises(ValueError, match="Tool failed"):
                    failing_tool()

                # Even after exception, should be back to initial state
                assert get_agent_id() == "initial-agent"
        finally:
            # Cleanup
            reset_agent_id(initial_token)

    def test_with_agent_id_isolation_between_calls(self):
        """R5: Multiple calls with different agent_ids don't leak."""
        # Ensure clean initial state
        set_agent_id(None)

        @with_agent_id
        def tool_with_agent():
            return get_agent_id()

        # First call
        with patch("task_orchestrator.server._resolve_agent_id") as mock_resolve:
            mock_resolve.return_value = "agent-one"
            result_one = tool_with_agent()
            assert result_one == "agent-one"

        # Second call with different agent
        with patch("task_orchestrator.server._resolve_agent_id") as mock_resolve:
            mock_resolve.return_value = "agent-two"
            result_two = tool_with_agent()
            assert result_two == "agent-two"

        # Outside both calls, should be None (default)
        assert get_agent_id() is None


class TestBoundaryIntegration:
    """Integration test for boundary resolution using actual engine operations."""

    def test_create_item_with_resolved_agent_id(self):
        """Integration: Tool boundary resolves agent_id and item gets created_by."""

        # Clear any existing agent_id
        set_agent_id(None)

        # Mock the resolution to return a specific agent_id
        with patch("task_orchestrator.server._resolve_agent_id") as mock_resolve:
            mock_resolve.return_value = "boundary-test"

            # Use the decorated manage_items function
            from task_orchestrator.server import manage_items

            # Call the tool (which should resolve and set agent_id)
            result_json = manage_items(
                operation="create",
                title="Boundary Test Item",
                description="Test item for boundary resolution",
            )

            # Parse result
            import json

            result = json.loads(result_json)

            # Item should have created_by from resolved agent_id
            assert result["created_by"] == "boundary-test"

        # After tool execution, agent_id should be reset
        assert get_agent_id() is None
