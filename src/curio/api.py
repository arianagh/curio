from ninja import NinjaAPI

from accounts.api import router as auth_router

api = NinjaAPI()

api.add_router("/auth", auth_router, tags=["auth"])


@api.get("/health")
def health(request):
    return {"status": "ok"}
