"""OAuth2 resource-server authentication with opaque pre-shared tokens.

Implements TokenVerifier interface for MCP FastMCP auth.
"""

import hmac
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings


class OpaqueTokenVerifier:
    """Token verifier for opaque pre-shared tokens."""

    def __init__(self, persona_secrets: dict[str, str] | None = None) -> None:
        """Initialize with persona->secret mapping.

        Args:
            persona_secrets: Dict of persona names to their secrets.
                            If None, will read from MCP_OAUTH_TOKENS env var.
        """
        if persona_secrets is None:
            self.persona_secrets = self._load_tokens_from_env()
        else:
            self.persona_secrets = persona_secrets

    def _load_tokens_from_env(self) -> dict[str, str]:
        """Load persona->secret mapping from MCP_OAUTH_TOKENS environment variable.

        Expected format: "persona1:secret1,persona2:secret2"
        """
        tokens_env = os.environ.get("MCP_OAUTH_TOKENS", "")
        if not tokens_env:
            return {}

        result = {}
        for pair in tokens_env.split(","):
            if ":" not in pair:
                continue
            persona, secret = pair.split(":", 1)
            result[persona.strip()] = secret.strip()
        return result

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify bearer token against configured secrets.

        Args:
            token: Bearer token to verify

        Returns:
            AccessToken if valid, None if invalid/empty
        """
        if not token:
            return None

        # Check against all configured secrets using constant-time comparison
        for persona, secret in self.persona_secrets.items():
            if hmac.compare_digest(token, secret):
                return AccessToken(
                    token=token, client_id=persona, scopes=["orc"], expires_at=None
                )

        return None


def build_auth() -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Build auth configuration from environment variables.

    Returns:
        Tuple of (TokenVerifier, AuthSettings) if OAuth is enabled,
        (None, None) if disabled.
    """
    # Check if OAuth is enabled
    oauth_enabled = os.environ.get("MCP_OAUTH_ENABLED", "").lower()
    if oauth_enabled not in ("true", "1", "yes"):
        return (None, None)

    # Create token verifier
    verifier = OpaqueTokenVerifier()

    # Build AuthSettings with required fields
    issuer_url = os.environ.get("MCP_OAUTH_ISSUER", "https://cfnarede.dev/orc")
    resource_server_url = os.environ.get("MCP_OAUTH_RESOURCE_SERVER_URL", issuer_url)

    auth_settings = AuthSettings(
        issuer_url=issuer_url,
        resource_server_url=resource_server_url,
        required_scopes=["orc"],
    )

    return (verifier, auth_settings)
