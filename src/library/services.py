import re
from dataclasses import dataclass

import httpx
from django.conf import settings

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class FetchedArticle:
    title: str
    content: str
    summary: str


def fetch_and_summarize(url: str) -> FetchedArticle:
    """Fetch a url and summarize it via Ollama. Raises httpx.HTTPError on any
    network/HTTP failure so callers can decide whether to retry."""
    page = httpx.get(url, timeout=10, follow_redirects=True)
    page.raise_for_status()
    html = page.text

    match = TITLE_RE.search(html)
    title = match.group(1).strip() if match else url

    summary_response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": "qwen3:8b",
            "prompt": f"Summarize the following in 2-3 sentences:\n\n{html[:4000]}",
            "stream": False,
        },
        timeout=60,
    )
    summary_response.raise_for_status()
    summary = summary_response.json().get("response", "").strip()

    return FetchedArticle(title=title, content=html, summary=summary)
