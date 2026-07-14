import pytest
from django.contrib.auth.models import User
from ninja_jwt.tokens import RefreshToken


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def user(db):
    return User.objects.create_user(username="alice", password="pw12345")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="bob", password="pw12345")


def bearer_header(user: User) -> dict[str, str]:
    token = RefreshToken.for_user(user)
    return {"Authorization": f"Bearer {token.access_token}"}  # type: ignore[attr-defined]


@pytest.fixture
def auth_header(user):
    return bearer_header(user)
