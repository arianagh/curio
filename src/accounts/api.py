from django.contrib.auth import authenticate
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.tokens import RefreshToken

from .schemas import TokenObtainIn, TokenPairOut

router = Router()


@router.post("/token", response=TokenPairOut)
def obtain_token(request, data: TokenObtainIn):
    user = authenticate(request, username=data.username, password=data.password)
    if user is None:
        raise HttpError(401, "Invalid credentials")
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}  # type: ignore[attr-defined]
