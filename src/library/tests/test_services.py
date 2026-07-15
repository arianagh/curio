import httpx
import pytest
import respx

from library.services import fetch_article


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
