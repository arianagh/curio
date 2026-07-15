import json

import httpx
import pytest
import respx
from django.conf import settings

from library.models import Article, Tag
from library.services import fetch_article, filter_articles, get_or_create_article


@respx.mock
def test_fetch_article_returns_title_and_content():
    url = "https://example.com/a"
    html = "<html><head><title>Hello World</title></head><body>hi</body></html>"
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = fetch_article(url)

    assert result.title == "Hello World"
    assert result.content == html


@respx.mock
def test_fetch_article_falls_back_to_url_when_title_tag_missing():
    url = "https://example.com/b"
    html = "<html><body>no title here</body></html>"
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = fetch_article(url)

    assert result.title == url


@respx.mock
def test_fetch_article_handles_title_tag_with_attributes_and_whitespace():
    url = "https://example.com/c"
    html = '<html><title lang="en">\n  Hello  \n</title></html>'
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = fetch_article(url)

    assert result.title == "Hello"


@respx.mock
def test_fetch_article_raises_http_error_on_5xx_response():
    url = "https://example.com/d"
    respx.get(url).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPError):
        fetch_article(url)


@respx.mock
def test_fetch_article_raises_http_error_on_connection_failure():
    url = "https://example.com/e"
    respx.get(url).mock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(httpx.HTTPError):
        fetch_article(url)


def _mock_ingest_success(url: str, title: str = "Example", summary: str = "A summary."):
    respx.get(url).mock(
        return_value=httpx.Response(200, text=f"<html><title>{title}</title></html>")
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"summary": summary, "tags": ["example"]}),
                }
            },
        )
    )
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1] * 768})
    )


@pytest.mark.django_db
def test_filter_articles_by_tag(user):
    tag_py = Tag.objects.create(owner=user, name="python")
    matching = Article.objects.create(owner=user, url="https://example.com/1")
    matching.tags.add(tag_py)
    Article.objects.create(owner=user, url="https://example.com/2")

    result = filter_articles(user, tag="python")

    assert {a.id for a in result} == {matching.id}


@pytest.mark.django_db
def test_filter_articles_by_q(user):
    matching = Article.objects.create(
        owner=user, url="https://example.com/1", title="Django tips"
    )
    Article.objects.create(owner=user, url="https://example.com/2", title="Cooking")

    result = filter_articles(user, q="django")

    assert {a.id for a in result} == {matching.id}


@pytest.mark.django_db
@respx.mock
def test_get_or_create_article_dedupes(user):
    url = "https://example.com/dupe"
    _mock_ingest_success(url)

    first, first_created = get_or_create_article(user, url)
    second, second_created = get_or_create_article(user, url)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert Article.objects.filter(owner=user, url=url).count() == 1


@pytest.mark.django_db
@respx.mock
def test_get_or_create_article_enqueues_ingest(user):
    url = "https://example.com/new"
    _mock_ingest_success(url)

    article, created = get_or_create_article(user, url)

    assert created is True
    article.refresh_from_db()
    assert article.status == Article.Status.ENRICHED
