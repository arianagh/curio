from uuid import UUID

from django.contrib.auth.models import User
from django.db.models import Q

from library.models import Article


def search_articles(user: User, query: str) -> list[Article]:
    """Reuses the same icontains filter as library.api.list_articles' `q`
    param, scoped to the authenticated owner."""
    return list(
        Article.objects.filter(owner=user)
        .filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(summary__icontains=query)
        )
        .distinct()
    )


def fetch_article(user: User, article_id: UUID) -> Article:
    """Raises Article.DoesNotExist on a missing id or one owned by another
    user — same 404-shaped behavior as the REST API's get_article."""
    return Article.objects.get(owner=user, id=article_id)
