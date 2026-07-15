import httpx
from django.conf import settings


def get_embedding(text: str) -> list[float]:
    """Embed text via Ollama's embeddings API.

    Raises httpx.HTTPError on any network/HTTP failure (including an
    unreachable Ollama), same contract as enrich(), so callers reuse the
    same retry-or-fail decision points.
    """
    response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
        json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["embedding"]
