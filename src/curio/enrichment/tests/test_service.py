import httpx
import pytest
import respx
from django.conf import settings

from curio.enrichment.schemas import EnrichmentResult
from curio.enrichment.service import enrich


@respx.mock
def test_enrich_returns_valid_schema():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '{"summary": "A short summary.", '
                    '"tags": ["django", "celery", "ollama"]}',
                }
            },
        )
    )

    result = enrich("<html>some article text</html>")

    assert isinstance(result, EnrichmentResult)
    assert result.summary
    assert len(result.tags) > 0


@respx.mock
def test_enrich_raises_http_error_when_ollama_unreachable():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(httpx.HTTPError):
        enrich("<html>some article text</html>")


@respx.mock
def test_enrich_raises_http_error_on_5xx_response():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(httpx.HTTPError):
        enrich("<html>some article text</html>")


@respx.mock
def test_enrich_raises_on_malformed_json_response():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "not valid json",
                }
            },
        )
    )

    with pytest.raises(ValueError):
        enrich("<html>some article text</html>")
