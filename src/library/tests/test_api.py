import json

import httpx
import pytest
import respx
from django.conf import settings

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
@respx.mock
def test_create_article_returns_202_and_pending(client, user, auth_header):
    url = "https://example.com/a"
    _mock_ingest_success(url)

    response = client.post(
        "/api/v1/articles",
        data={"url": url},
        content_type="application/json",
        headers=auth_header,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert Article.objects.filter(owner=user, url=url).count() == 1


@pytest.mark.django_db
@respx.mock
def test_create_article_duplicate_returns_existing(client, user, auth_header):
    url = "https://example.com/b"
    _mock_ingest_success(url)

    first = client.post(
        "/api/v1/articles",
        data={"url": url},
        content_type="application/json",
        headers=auth_header,
    )
    second = client.post(
        "/api/v1/articles",
        data={"url": url},
        content_type="application/json",
        headers=auth_header,
    )

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["status"] == "enriched"
    assert Article.objects.filter(owner=user, url=url).count() == 1


@pytest.mark.django_db
def test_list_articles_only_returns_owners_own(client, user, other_user, auth_header):
    Article.objects.create(owner=other_user, url="https://example.com/other")
    mine = Article.objects.create(owner=user, url="https://example.com/mine")

    response = client.get("/api/v1/articles", headers=auth_header)

    ids = {item["id"] for item in response.json()}
    assert ids == {str(mine.id)}


@pytest.mark.django_db
def test_list_articles_filters_by_tag_and_q(client, user, auth_header):
    tag_py = Tag.objects.create(owner=user, name="python")
    a1 = Article.objects.create(
        owner=user, url="https://example.com/1", title="Django tips"
    )
    a1.tags.add(tag_py)
    a2 = Article.objects.create(
        owner=user, url="https://example.com/2", title="Cooking pasta"
    )
    a3 = Article.objects.create(
        owner=user, url="https://example.com/3", title="Python async"
    )
    a3.tags.add(tag_py)

    by_tag = client.get("/api/v1/articles", {"tag": "python"}, headers=auth_header)
    assert {item["id"] for item in by_tag.json()} == {str(a1.id), str(a3.id)}

    by_q = client.get("/api/v1/articles", {"q": "pasta"}, headers=auth_header)
    assert {item["id"] for item in by_q.json()} == {str(a2.id)}

    by_both = client.get(
        "/api/v1/articles", {"tag": "python", "q": "async"}, headers=auth_header
    )
    assert {item["id"] for item in by_both.json()} == {str(a3.id)}


@pytest.mark.django_db
def test_get_article_404_for_other_owner(client, user, other_user, auth_header):
    other_article = Article.objects.create(
        owner=other_user, url="https://example.com/other"
    )

    response = client.get(f"/api/v1/articles/{other_article.id}", headers=auth_header)

    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_article(client, user, auth_header):
    article = Article.objects.create(owner=user, url="https://example.com/del")

    response = client.delete(f"/api/v1/articles/{article.id}", headers=auth_header)

    assert response.status_code == 204
    assert not Article.objects.filter(id=article.id).exists()


@pytest.mark.django_db
def test_delete_article_404_for_other_owner(client, user, other_user, auth_header):
    other_article = Article.objects.create(
        owner=other_user, url="https://example.com/other"
    )

    response = client.delete(
        f"/api/v1/articles/{other_article.id}", headers=auth_header
    )

    assert response.status_code == 404
    assert Article.objects.filter(id=other_article.id).exists()


@pytest.mark.django_db
def test_list_tags_owner_scoped(client, user, other_user, auth_header):
    Tag.objects.create(owner=user, name="python")
    Tag.objects.create(owner=other_user, name="rust")

    response = client.get("/api/v1/tags", headers=auth_header)

    assert {item["name"] for item in response.json()} == {"python"}


@pytest.mark.django_db
def test_list_articles_requires_auth(client):
    response = client.get("/api/v1/articles")

    assert response.status_code == 401


@pytest.mark.django_db
def test_similar_to_ranks_closer_embedding_first(client, user, auth_header):
    same_vector = [1.0] + [0.0] * 767
    orthogonal_vector = [0.0, 1.0] + [0.0] * 766

    source = Article.objects.create(
        owner=user,
        url="https://example.com/source",
        title="Unrelated title",
        summary="Unrelated summary",
        status=Article.Status.ENRICHED,
        embedding=same_vector,
    )
    close = Article.objects.create(
        owner=user,
        url="https://example.com/close",
        title="Something else",
        summary="Something else entirely",
        status=Article.Status.ENRICHED,
        embedding=same_vector,
    )
    far = Article.objects.create(
        owner=user,
        url="https://example.com/far",
        title="Something else",
        summary="Something else entirely",
        status=Article.Status.ENRICHED,
        embedding=orthogonal_vector,
    )

    response = client.get(
        "/api/v1/articles",
        {"similar_to": str(source.id)},
        headers=auth_header,
    )

    ids = [item["id"] for item in response.json()]
    assert str(source.id) not in ids
    assert ids.index(str(close.id)) < ids.index(str(far.id))


@pytest.mark.django_db
def test_similar_to_is_owner_scoped(client, user, other_user, auth_header):
    other_article = Article.objects.create(
        owner=other_user,
        url="https://example.com/other-source",
        status=Article.Status.ENRICHED,
        embedding=[0.1] * 768,
    )

    response = client.get(
        "/api/v1/articles",
        {"similar_to": str(other_article.id)},
        headers=auth_header,
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_similar_to_404_without_embedding(client, user, auth_header):
    no_embedding = Article.objects.create(
        owner=user,
        url="https://example.com/no-embedding",
        status=Article.Status.ENRICHED,
    )

    response = client.get(
        "/api/v1/articles",
        {"similar_to": str(no_embedding.id)},
        headers=auth_header,
    )

    assert response.status_code == 404
