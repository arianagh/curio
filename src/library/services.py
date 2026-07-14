import re
from dataclasses import dataclass

import httpx

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class FetchedArticle:
    title: str
    content: str


def fetch_article(url: str) -> FetchedArticle:
    """Fetch a url and parse its title. Raises httpx.HTTPError on any
    network/HTTP failure so callers can decide whether to retry."""
    page = httpx.get(url, timeout=10, follow_redirects=True)
    page.raise_for_status()
    html = page.text

    match = TITLE_RE.search(html)
    title = match.group(1).strip() if match else url

    return FetchedArticle(title=title, content=html)
