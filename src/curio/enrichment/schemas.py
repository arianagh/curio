from pydantic import BaseModel


class EnrichmentResult(BaseModel):
    summary: str
    tags: list[str]
