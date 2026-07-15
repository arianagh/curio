import pytest

from library.models import Article
from library.tests.factories import ArticleFactory, UserFactory
from mcp_server.service import fetch_article, search_articles


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


@pytest.mark.django_db
def test_fetch_article_returns_owned_article():
    user = UserFactory()
    article = ArticleFactory(owner=user)

    assert fetch_article(user, article.id) == article


@pytest.mark.django_db
def test_fetch_article_raises_for_other_owners_article():
    user = UserFactory()
    other = UserFactory()
    article = ArticleFactory(owner=other)

    with pytest.raises(Article.DoesNotExist):
        fetch_article(user, article.id)
