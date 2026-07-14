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

    ingest_article.delay(str(article.id))

    article.refresh_from_db()
    assert article.status == Article.Status.ENRICHED
    assert article.title == "Hello"
    assert article.summary == "A short summary."
    assert article.fetched_at is not None


@pytest.mark.django_db
@respx.mock
def test_ingest_article_retries_then_succeeds(user, settings):
    # A real retry raises celery.exceptions.Retry, which eager mode normally
    # re-raises to the caller (task_eager_propagates=True, set for tests in
    # conftest.py) instead of transparently re-running the task. Turn that off
    # here so `.delay()` actually loops through the retry like a worker would.
    settings.CELERY_TASK_EAGER_PROPAGATES = False
    article = Article.objects.create(owner=user, url="https://example.com/b")
    route = respx.get("https://example.com/b")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, text="<html><title>Recovered</title></html>"),
    ]
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "A short summary."})
    )

    ingest_article.delay(str(article.id))

    article.refresh_from_db()
    assert route.call_count == 2
    assert article.status == Article.Status.ENRICHED
    assert article.title == "Recovered"


@pytest.mark.django_db
@respx.mock
def test_ingest_article_marks_failed_after_exhausting_retries(user, settings):
    settings.CELERY_TASK_EAGER_PROPAGATES = False
    article = Article.objects.create(owner=user, url="https://example.com/c")
    route = respx.get("https://example.com/c").mock(return_value=httpx.Response(500))

    ingest_article.delay(str(article.id))

    article.refresh_from_db()
    assert route.call_count == 4  # initial attempt + 3 retries
    assert article.status == Article.Status.FAILED


@pytest.mark.django_db
@respx.mock
def test_ingest_article_is_noop_when_already_enriched(user):
    article = Article.objects.create(
        owner=user,
        url="https://example.com/d",
        status=Article.Status.ENRICHED,
        title="Already done",
    )
    route = respx.get("https://example.com/d")

    ingest_article.delay(str(article.id))

    article.refresh_from_db()
    assert route.call_count == 0
    assert article.title == "Already done"
