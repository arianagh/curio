"""MCP server exposing a user's curio library over stdio.

Run directly: `uv run python mcp_server/server.py`. Requires CURIO_MCP_TOKEN
(a refresh token from POST /api/v1/auth/token) in the environment.
"""

import os
import sys
from pathlib import Path
from uuid import UUID

import django
from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "curio.settings")
django.setup()

from library.models import Article  # noqa: E402
from mcp_server.auth import AuthConfigError, resolve_user  # noqa: E402
from mcp_server.service import fetch_article, search_articles  # noqa: E402

mcp = FastMCP("curio-library")

try:
    _user = resolve_user()
except AuthConfigError as exc:
    print(f"curio-library MCP server: {exc}", file=sys.stderr)
    sys.exit(1)


def _serialize_summary(article: Article) -> dict:
    return {
        "id": str(article.id),
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "tags": [tag.name for tag in article.tags.all()],
        "created_at": article.created_at.isoformat(),
    }


@mcp.tool()
async def search_library(query: str) -> list[dict]:
    """Search the current user's saved articles by title, content, or summary."""
    articles = await sync_to_async(search_articles, thread_sensitive=True)(_user, query)
    return [_serialize_summary(article) for article in articles]


@mcp.tool()
async def get_article(id: str) -> dict:
    """Fetch one saved article by id, including its full content."""
    try:
        article = await sync_to_async(fetch_article, thread_sensitive=True)(
            _user, UUID(id)
        )
    except (Article.DoesNotExist, ValueError) as exc:
        raise ValueError(f"No article found with id {id!r}") from exc

    return {
        **_serialize_summary(article),
        "content": article.content,
        "status": article.status,
    }


if __name__ == "__main__":
    mcp.run()
