"""Real-stack smoke test for the E2E workflow.

Runs against a live API server + Celery worker + Ollama (see
.github/workflows/e2e.yml) — not pytest, since the point is to exercise the
real worker/broker/network path that mocked tests skip. Exits non-zero on
any failure so the workflow step fails loudly.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import django  # noqa: E402

import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "curio.settings")
django.setup()

import httpx  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from ninja_jwt.tokens import RefreshToken  # noqa: E402

BASE_URL = "http://localhost:8000/api/v1"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 240


def get_auth_header() -> dict[str, str]:
    user, _ = User.objects.get_or_create(username="e2e-smoke")
    token = RefreshToken.for_user(user)
    return {"Authorization": f"Bearer {token.access_token}"}  # type: ignore[attr-defined]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    client = httpx.Client(
        base_url=BASE_URL,
        headers={**get_auth_header(), "Content-Type": "application/json"},
        timeout=30,
    )

    print("POST /articles")
    response = client.post("/articles", json={"url": "https://example.com"})
    response.raise_for_status()
    article = response.json()
    article_id = article["id"]
    print(f"  -> {response.status_code} id={article_id} status={article['status']!r}")

    elapsed = 0
    while article["status"] not in ("enriched", "failed"):
        if elapsed >= POLL_TIMEOUT_SECONDS:
            fail(
                f"timed out after {POLL_TIMEOUT_SECONDS}s waiting for "
                f"enrichment (last status: {article['status']!r})"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
        response = client.get(f"/articles/{article_id}")
        response.raise_for_status()
        article = response.json()
        print(f"  [{elapsed}s] status={article['status']!r}")

    if article["status"] == "failed":
        fail("article ingest ended in 'failed' status")

    summary, tags = article["summary"], article["tags"]
    print(f"  summary: {summary!r}")
    print(f"  tags: {tags}")
    if not summary.strip():
        fail("enriched article has an empty summary")
    if not tags:
        fail("enriched article has no tags")

    # ArticleOut doesn't expose the embedding directly, but ?similar_to= 404s
    # unless embedding__isnull=False (see library/api.py) — a 200 here is
    # proof the embedding actually landed, not just that status flipped.
    print(f"GET /articles?similar_to={article_id}")
    response = client.get("/articles", params={"similar_to": article_id})
    if response.status_code != 200:
        fail(
            f"expected embedding to be set, similar_to returned {response.status_code}"
        )

    query_term = summary.split()[0]
    print(f"GET /articles?q={query_term!r}")
    response = client.get("/articles", params={"q": query_term})
    response.raise_for_status()
    if not any(a["id"] == article_id for a in response.json()):
        fail(f"article {article_id} not found via ?q={query_term!r}")

    print("E2E smoke test passed.")


if __name__ == "__main__":
    main()
