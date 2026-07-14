from datetime import datetime
from uuid import UUID

from ninja import Schema


class ArticleCreateIn(Schema):
    url: str


class ArticleOut(Schema):
    id: UUID
    url: str
    title: str
    summary: str
    status: str
    tags: list[str]
    fetched_at: datetime | None
    created_at: datetime

    @staticmethod
    def resolve_tags(obj) -> list[str]:
        return [tag.name for tag in obj.tags.all()]


class TagOut(Schema):
    id: UUID
    name: str
