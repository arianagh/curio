import hashlib
import uuid

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, Q, Window
from django.db.models.functions import Rank
from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja_jwt.authentication import JWTAuth
from pgvector.django import CosineDistance

from .models import Article, Tag
from .schemas import ArticleCreateIn, ArticleOut, TagOut
from .tasks import ingest_article

SIMILAR_TO_LIMIT = 20
RRF_K = 60

articles_router = Router(auth=JWTAuth())
tags_router = Router(auth=JWTAuth())


@articles_router.post("", response={200: ArticleOut, 202: ArticleOut})
def create_article(request, data: ArticleCreateIn):
    url_hash = hashlib.sha256(data.url.encode()).hexdigest()
    existing = Article.objects.filter(owner=request.auth, url_hash=url_hash).first()
    if existing is not None:
        return Status(200, existing)

    article = Article.objects.create(owner=request.auth, url=data.url)
    ingest_article.delay(str(article.id))
    return Status(202, article)


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

    if tag:
        queryset = queryset.filter(tags__owner=request.auth, tags__name=tag)

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) | Q(content__icontains=q) | Q(summary__icontains=q)
        )

    return queryset.distinct()


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
