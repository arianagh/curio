import logging

import httpx
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Article
from .services import fetch_and_summarize

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def ingest_article(self, article_id: str) -> None:
    try:
        with transaction.atomic():
            article = Article.objects.select_for_update().get(id=article_id)
            if article.status == Article.Status.ENRICHED:
                logger.info(
                    "ingest_article: article_id=%s already enriched, skipping",
                    article_id,
                )
                return
            article.status = Article.Status.FETCHING
            article.save(update_fields=["status", "updated_at"])
    except Article.DoesNotExist:
        logger.warning("ingest_article: no article with id=%s", article_id)
        return

    try:
        result = fetch_and_summarize(article.url)
    except httpx.HTTPError as exc:
        if self.request.retries >= self.max_retries:
            logger.exception(
                "ingest_article: exhausted retries for article_id=%s", article_id
            )
            article.status = Article.Status.FAILED
            article.save(update_fields=["status", "updated_at"])
            return
        raise self.retry(exc=exc)
    except Exception:
        logger.exception("ingest_article: failed for article_id=%s", article_id)
        article.status = Article.Status.FAILED
        article.save(update_fields=["status", "updated_at"])
        return

    article.title = result.title
    article.content = result.content
    article.summary = result.summary
    article.status = Article.Status.ENRICHED
    article.fetched_at = timezone.now()
    article.save(
        update_fields=[
            "title",
            "content",
            "summary",
            "status",
            "fetched_at",
            "updated_at",
        ]
    )
