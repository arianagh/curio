import logging

import httpx
from django.core.management.base import BaseCommand

from curio.enrichment.embeddings import get_embedding
from library.models import Article

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill embeddings for enriched articles that don't have one yet."

    def handle(self, *args, **options):
        queryset = Article.objects.filter(
            embedding__isnull=True, status=Article.Status.ENRICHED
        )
        total = queryset.count()
        done = 0
        failed = 0

        for article in queryset.iterator():
            try:
                embedding = get_embedding(f"{article.title}\n\n{article.summary}")
            except httpx.HTTPError:
                logger.exception(
                    "backfill_embeddings: failed for article_id=%s", article.id
                )
                failed += 1
                continue

            article.embedding = embedding
            article.save(update_fields=["embedding"])
            done += 1

        self.stdout.write(
            f"Backfilled {done}/{total} articles ({failed} failed, left for next run)."
        )
