from ninja import NinjaAPI

from accounts.api import router as auth_router
from library.api import articles_router, tags_router

api = NinjaAPI(
    title="Curio API",
    version="1.0.0",
    description="Save a url, get it fetched, summarized, and tagged.",
)

api.add_router("/auth", auth_router, tags=["auth"])
api.add_router("/articles", articles_router, tags=["articles"])
api.add_router("/tags", tags_router, tags=["tags"])


@api.get("/health")
def health(request):
    return {"status": "ok"}
