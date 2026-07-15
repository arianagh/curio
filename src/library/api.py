import uuid

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, Window
from django.db.models.functions import Rank
from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja_jwt.authentication import JWTAuth
from pgvector.django import CosineDistance

from .models import Article, Tag
from .schemas import ArticleCreateIn, ArticleOut, TagOut
from .services import filter_articles, get_or_create_article

SIMILAR_TO_LIMIT = 20
RRF_K = 60

articles_router = Router(auth=JWTAuth())
tags_router = Router(auth=JWTAuth())


@articles_router.post("", response={200: ArticleOut, 202: ArticleOut})
def create_article(request, data: ArticleCreateIn):
    article, created = get_or_create_article(request.auth, data.url)
    return Status(202 if created else 200, article)


@articles_router.get("", response=list[ArticleOut])
def list_articles(
    request,
    tag: str | None = None,
    q: str | None = None,
    similar_to: uuid.UUID | None = None,
):
    queryset = Article.objects.filter(owner=request.auth)

    if similar_to:
        source = get_object_or_404(queryset, id=similar_to, embedding__isnull=False)
        candidates = queryset.exclude(id=source.id)
        search_vector = SearchVector("title", "summary", "content")
        search_query = SearchQuery(f"{source.title} {source.summary}")

        candidates = candidates.annotate(
            rank_fts=Window(
                expression=Rank(),
                order_by=SearchRank(search_vector, search_query).desc(),
            ),
            rank_vec=Window(
                expression=Rank(),
                order_by=CosineDistance("embedding", source.embedding).asc(),
            ),
        ).annotate(
            rrf_score=1.0 / (RRF_K + F("rank_fts")) + 1.0 / (RRF_K + F("rank_vec"))
        )
        return candidates.order_by("-rrf_score")[:SIMILAR_TO_LIMIT]

    return filter_articles(request.auth, tag=tag, q=q)


@articles_router.get("/{article_id}", response=ArticleOut)
def get_article(request, article_id: uuid.UUID):
    return get_object_or_404(Article, id=article_id, owner=request.auth)


@articles_router.delete("/{article_id}", response={204: None})
def delete_article(request, article_id: uuid.UUID):
    article = get_object_or_404(Article, id=article_id, owner=request.auth)
    article.delete()
    return Status(204, None)


@tags_router.get("", response=list[TagOut])
def list_tags(request):
    return Tag.objects.filter(owner=request.auth)
