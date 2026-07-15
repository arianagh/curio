import pytest

from library.tests.factories import ArticleFactory, UserFactory
from mcp_server.service import search_articles


@pytest.mark.django_db
def test_search_articles_matches_title():
    user = UserFactory()
    ArticleFactory(owner=user, title="Django internals", content="", summary="")
    ArticleFactory(owner=user, title="Cooking pasta", content="", summary="")

    results = search_articles(user, "django")

    assert [a.title for a in results] == ["Django internals"]


@pytest.mark.django_db
def test_search_articles_matches_content_or_summary():
    user = UserFactory()
    ArticleFactory(owner=user, title="Untitled", content="all about django", summary="")

    results = search_articles(user, "django")

    assert len(results) == 1


@pytest.mark.django_db
def test_search_articles_scoped_to_owner():
    user = UserFactory()
    other = UserFactory()
    ArticleFactory(owner=other, title="Django internals", content="", summary="")

    results = search_articles(user, "django")

    assert results == []
