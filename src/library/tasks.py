import logging
import re

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Article

logger = logging.getLogger(__name__)

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@shared_task
def ingest_article(article_id: str) -> None:
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        logger.warning("ingest_article: no article with id=%s", article_id)
        return

    article.status = Article.Status.FETCHING
    article.save(update_fields=["status"])

    try:
        page = httpx.get(article.url, timeout=10, follow_redirects=True)
        page.raise_for_status()
        html = page.text

        match = TITLE_RE.search(html)
        title = match.group(1).strip() if match else article.url

        summary_response = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": "qwen3:8b",
                "prompt": f"Summarize the following in 2-3 sentences:\n\n{html[:4000]}",
                "stream": False,
            },
            timeout=60,
        )
        summary_response.raise_for_status()
        summary = summary_response.json().get("response", "").strip()
    except Exception:
        logger.exception("ingest_article: failed for article_id=%s", article_id)
        article.status = Article.Status.FAILED
        article.save(update_fields=["status"])
        return

    article.title = title
    article.content = html
    article.summary = summary
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
