import pytest
from ninja_jwt.tokens import RefreshToken

from library.tests.factories import UserFactory
from mcp_server.auth import TOKEN_ENV_VAR, AuthConfigError, resolve_user


@pytest.mark.django_db
def test_resolve_user_returns_user_for_valid_token(monkeypatch):
    user = UserFactory()
    token = str(RefreshToken.for_user(user))
    monkeypatch.setenv(TOKEN_ENV_VAR, token)

    assert resolve_user() == user


def test_resolve_user_raises_when_token_env_var_missing(monkeypatch):
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)

    with pytest.raises(AuthConfigError, match="not set"):
        resolve_user()


def test_resolve_user_raises_for_garbage_token(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "not-a-real-token")

    with pytest.raises(AuthConfigError, match="invalid or expired"):
        resolve_user()


@pytest.mark.django_db
def test_resolve_user_raises_when_user_deleted(monkeypatch):
    user = UserFactory()
    token = str(RefreshToken.for_user(user))
    user.delete()
    monkeypatch.setenv(TOKEN_ENV_VAR, token)

    with pytest.raises(AuthConfigError, match="no longer exists"):
        resolve_user()
