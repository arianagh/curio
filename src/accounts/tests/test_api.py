import pytest


@pytest.mark.django_db
def test_obtain_token_with_valid_credentials(client, user):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "alice", "password": "pw12345"},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert "refresh" in body


@pytest.mark.django_db
def test_obtain_token_with_invalid_credentials(client, user):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "alice", "password": "wrong"},
        content_type="application/json",
    )

    assert response.status_code == 401
