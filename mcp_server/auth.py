import os

from django.contrib.auth.models import User
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

TOKEN_ENV_VAR = "CURIO_MCP_TOKEN"


class AuthConfigError(Exception):
    """Raised when CURIO_MCP_TOKEN is missing, invalid, or expired."""


def resolve_user() -> User:
    """Resolve the Django user this MCP server acts as, from the refresh
    token in CURIO_MCP_TOKEN. Called once at server startup."""
    raw_token = os.environ.get(TOKEN_ENV_VAR)
    if not raw_token:
        raise AuthConfigError(
            f"{TOKEN_ENV_VAR} is not set. Mint one with "
            "POST /api/v1/auth/token (username + password) and export the "
            "`refresh` value from the response."
        )

    try:
        token = RefreshToken(raw_token)
        user_id = token["user_id"]
    except TokenError as exc:
        raise AuthConfigError(
            f"{TOKEN_ENV_VAR} is invalid or expired — mint a fresh one with "
            "POST /api/v1/auth/token."
        ) from exc

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise AuthConfigError(
            f"{TOKEN_ENV_VAR} refers to a user that no longer exists."
        ) from exc
