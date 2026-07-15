import json

import httpx
import pytest
import respx
from django.conf import settings
from django.urls import reverse

from library.models import Article, Tag


def _mock_ingest_success(url: str, title: str = "Example", summary: str = "A summary."):
    respx.get(url).mock(
        return_value=httpx.Response(200, text=f"<html><title>{title}</title></html>")
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"summary": summary, "tags": ["example"]}),
                }
            },
        )
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1] * 768})
    )


@pytest.mark.django_db
def test_article_list_requires_login(client):
    response = client.get(reverse("ui:article_list"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("ui:login"))


@pytest.mark.django_db
def test_article_list_shows_only_owned_articles(client, user, other_user):
    Article.objects.create(owner=other_user, url="https://example.com/other")
    Article.objects.create(owner=user, url="https://example.com/mine", title="Mine")
    client.force_login(user)

    response = client.get(reverse("ui:article_list"))

    content = response.content.decode()
    assert "Mine" in content
    assert "https://example.com/other" not in content


@pytest.mark.django_db
def test_article_list_filters_by_tag_and_q(client, user):
    tag_py = Tag.objects.create(owner=user, name="python")
    matching = Article.objects.create(
        owner=user, url="https://example.com/1", title="Django tips"
    )
    matching.tags.add(tag_py)
    Article.objects.create(owner=user, url="https://example.com/2", title="Cooking")
    client.force_login(user)

    response = client.get(reverse("ui:article_list"), {"tag": "python"})
    content = response.content.decode()
    assert "Django tips" in content
    assert "Cooking" not in content


@pytest.mark.django_db
@respx.mock
def test_article_add_enqueues_ingest_and_returns_row_fragment(client, user):
    url = "https://example.com/new"
    _mock_ingest_success(url)
    client.force_login(user)

    response = client.post(
        reverse("ui:article_add"), {"url": url}, headers={"HX-Request": "true"}
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "<html" not in content
    assert Article.objects.filter(owner=user, url=url).exists()


@pytest.mark.django_db
def test_article_add_rejects_invalid_url(client, user):
    client.force_login(user)

    response = client.post(
        reverse("ui:article_add"),
        {"url": "not-a-url"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Enter a valid" in response.content.decode()
    assert not Article.objects.filter(owner=user).exists()


@pytest.mark.django_db
def test_article_delete_removes_article(client, user, other_user):
    article = Article.objects.create(owner=user, url="https://example.com/del")
    client.force_login(user)

    response = client.delete(reverse("ui:article_delete", args=[article.id]))

    assert response.status_code == 200
    assert not Article.objects.filter(id=article.id).exists()


@pytest.mark.django_db
def test_article_delete_404_for_other_owner(client, user, other_user):
    other_article = Article.objects.create(
        owner=other_user, url="https://example.com/other"
    )
    client.force_login(user)

    response = client.delete(reverse("ui:article_delete", args=[other_article.id]))

    assert response.status_code == 404
    assert Article.objects.filter(id=other_article.id).exists()


@pytest.mark.django_db
def test_article_status_polls_while_pending(client, user):
    article = Article.objects.create(
        owner=user, url="https://example.com/p", status=Article.Status.PENDING
    )
    client.force_login(user)

    response = client.get(reverse("ui:article_status", args=[article.id]))

    assert "hx-trigger" in response.content.decode()


@pytest.mark.django_db
def test_article_status_stops_polling_once_enriched(client, user):
    article = Article.objects.create(
        owner=user, url="https://example.com/e", status=Article.Status.ENRICHED
    )
    client.force_login(user)

    response = client.get(reverse("ui:article_status", args=[article.id]))

    assert "hx-trigger" not in response.content.decode()


@pytest.mark.django_db
def test_login_view_renders(client):
    response = client.get(reverse("ui:login"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_login_view_authenticates_with_valid_credentials(client, user):
    response = client.post(
        reverse("ui:login"), {"username": user.username, "password": "pw12345"}
    )

    assert response.status_code == 302
    assert response.url == reverse("ui:article_list")


@pytest.mark.django_db
def test_login_view_rejects_invalid_credentials(client, user):
    response = client.post(
        reverse("ui:login"), {"username": user.username, "password": "wrong"}
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
