from ninja import Schema


class TokenObtainIn(Schema):
    username: str
    password: str


class TokenPairOut(Schema):
    access: str
    refresh: str
