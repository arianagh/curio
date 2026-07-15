import hashlib
import re
from dataclasses import dataclass

import httpx
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

from .models import Article

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class FetchedArticle:
    title: str
    content: str


def fetch_article(url: str) -> FetchedArticle:
    """Fetch a url and parse its title. Raises httpx.HTTPError on any
    network/HTTP failure so callers can decide whether to retry."""
    page = httpx.get(url, timeout=10, follow_redirects=True)
    page.raise_for_status()
    html = page.text

    match = TITLE_RE.search(html)
    title = match.group(1).strip() if match else url

    return FetchedArticle(title=title, content=html)


def filter_articles(
    owner: User, *, tag: str | None = None, q: str | None = None
) -> QuerySet[Article]:
    queryset = Article.objects.filter(owner=owner)

    if tag:
        queryset = queryset.filter(tags__owner=owner, tags__name=tag)

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) | Q(content__icontains=q) | Q(summary__icontains=q)
        )

    return queryset.distinct()


def get_or_create_article(owner: User, url: str) -> tuple[Article, bool]:
    """Return the owner's existing article for this url, or create one and
    enqueue ingestion. The bool is True when a new article was created."""
    from .tasks import ingest_article

    url_hash = hashlib.sha256(url.encode()).hexdigest()
    existing = Article.objects.filter(owner=owner, url_hash=url_hash).first()
    if existing is not None:
        return existing, False

    article = Article.objects.create(owner=owner, url=url)
    ingest_article.delay(str(article.id))
    return article, True
