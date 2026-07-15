import httpx
import pytest
import respx
from django.conf import settings

from curio.enrichment.embeddings import get_embedding


@respx.mock
def test_get_embedding_returns_vector():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
    )

    result = get_embedding("some article text")

    assert result == [0.1, 0.2, 0.3]


@respx.mock
def test_get_embedding_raises_http_error_when_ollama_unreachable():
    respx.post(f"{settings.OLLAMA_BASE_URL}/api/embeddings").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(httpx.HTTPError):
        get_embedding("some article text")
