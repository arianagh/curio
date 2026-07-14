import httpx
import pytest
import respx
from django.conf import settings

from library.models import Article
from library.tasks import ingest_article


@pytest.mark.django_db
@respx.mock
def test_ingest_article_success(user):
    article = Article.objects.create(owner=user, url="https://example.com/a")
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(200, text="<html><title>Hello</title></html>")
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "A short summary."})
    )

    ingest_article(str(article.id))

    article.refresh_from_db()
    assert article.status == Article.Status.ENRICHED
    assert article.title == "Hello"
    assert article.summary == "A short summary."
    assert article.fetched_at is not None


@pytest.mark.django_db
@respx.mock
def test_ingest_article_marks_failed_on_fetch_error(user):
    article = Article.objects.create(owner=user, url="https://example.com/b")
    respx.get("https://example.com/b").mock(return_value=httpx.Response(500))

    ingest_article(str(article.id))

    article.refresh_from_db()
    assert article.status == Article.Status.FAILED
