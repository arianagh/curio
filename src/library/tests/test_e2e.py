import json

import httpx
import pytest
import respx
from django.conf import settings

from library.models import Article
from library.tests.factories import ArticleFactory, UserFactory


@pytest.mark.django_db
@respx.mock
def test_article_save_enrich_search_e2e(client, user, auth_header):
    url = "https://example.com/e2e-article"
    respx.get(url).mock(
        return_value=httpx.Response(
            200, text="<html><title>Deep Sea Robotics</title></html>"
        )
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "summary": "Autonomous submersibles are getting cheaper.",
                            "tags": ["robotics", "ocean"],
                        }
                    ),
                }
            },
        )
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1] * 768})
    )
    # A same-keyword article owned by someone else should never surface.
    other_user = UserFactory()
    ArticleFactory(
        owner=other_user,
        title="Submersibles Elsewhere",
        status=Article.Status.ENRICHED,
    )

    create_response = client.post(
        "/api/v1/articles",
        data={"url": url},
        content_type="application/json",
        headers=auth_header,
    )
    assert create_response.status_code == 202

    article = Article.objects.get(owner=user, url=url)
    assert article.status == Article.Status.ENRICHED
    assert article.title == "Deep Sea Robotics"
    assert article.embedding is not None

    search_response = client.get("/api/v1/articles?q=submersibles", headers=auth_header)
    assert search_response.status_code == 200
    results = search_response.json()
    assert [r["id"] for r in results] == [str(article.id)]
