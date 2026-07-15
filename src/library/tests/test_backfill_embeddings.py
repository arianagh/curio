import httpx
import pytest
import respx
from django.conf import settings
from django.core.management import call_command

from library.models import Article


@pytest.mark.django_db
@respx.mock
def test_backfill_embeds_pending_articles_and_skips_the_rest(user):
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.5] * 768})
    )
    pending = Article.objects.create(
        owner=user,
        url="https://example.com/pending",
        status=Article.Status.ENRICHED,
        title="Pending",
        summary="Needs an embedding.",
    )
    already_done = Article.objects.create(
        owner=user,
        url="https://example.com/done",
        status=Article.Status.ENRICHED,
        title="Done",
        summary="Already has one.",
        embedding=[0.1] * 768,
    )
    not_enriched = Article.objects.create(
        owner=user,
        url="https://example.com/not-enriched",
        status=Article.Status.PENDING,
    )

    call_command("backfill_embeddings")

    pending.refresh_from_db()
    already_done.refresh_from_db()
    not_enriched.refresh_from_db()
    assert list(pending.embedding) == pytest.approx([0.5] * 768)
    assert list(already_done.embedding) == pytest.approx([0.1] * 768)
    assert not_enriched.embedding is None


@pytest.mark.django_db
@respx.mock
def test_backfill_leaves_embedding_null_on_failure_for_next_run(user):
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    article = Article.objects.create(
        owner=user,
        url="https://example.com/flaky",
        status=Article.Status.ENRICHED,
        title="Flaky",
        summary="Ollama is down for this one.",
    )

    call_command("backfill_embeddings")

    article.refresh_from_db()
    assert article.embedding is None
