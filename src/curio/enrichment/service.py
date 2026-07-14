import httpx
from django.conf import settings

from .schemas import EnrichmentResult

SYSTEM_PROMPT = (
    "You read article text and produce a concise summary and topical tags. "
    "Respond only with JSON matching the given schema."
)


def enrich(content: str) -> EnrichmentResult:
    """Summarize article content and extract tags via Ollama's chat API.

    Raises httpx.HTTPError on any network/HTTP failure (including an
    unreachable Ollama) so callers can decide whether to retry, and lets a
    malformed response body raise as-is (pydantic ValidationError /
    json.JSONDecodeError) so callers can fail those immediately instead.
    """
    response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/chat",
        json={
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Article content:\n\n{content[:6000]}\n\n"
                        "Summarize this in 2-3 sentences and list 3-5 short "
                        "topical tags."
                    ),
                },
            ],
            "format": EnrichmentResult.model_json_schema(),
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()
    message_content = response.json()["message"]["content"]
    return EnrichmentResult.model_validate_json(message_content)
