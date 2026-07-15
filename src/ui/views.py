from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods

from library.models import Article, Tag
from library.services import filter_articles, get_or_create_article

CONTENT_PREVIEW_LENGTH = 2000
validate_article_url = URLValidator(schemes=["http", "https"])


@login_required
def article_list(request):
    tag = request.GET.get("tag")
    q = request.GET.get("q")
    articles = filter_articles(request.user, tag=tag, q=q)
    tags = Tag.objects.filter(owner=request.user)

    context = {"articles": articles, "tags": tags, "tag": tag, "q": q}
    template = (
        "ui/partials/_article_list.html" if request.htmx else "ui/article_list.html"
    )
    return render(request, template, context)


@login_required
@require_http_methods(["POST"])
def article_add(request):
    url = request.POST.get("url", "").strip()
    try:
        validate_article_url(url)
    except ValidationError:
        if request.htmx:
            return render(
                request,
                "ui/partials/_article_add_error.html",
                {"error": "Enter a valid http(s) URL."},
            )
        messages.error(request, "Enter a valid http(s) URL.")
        return redirect("ui:article_list")

    article, created = get_or_create_article(request.user, url)

    if request.htmx:
        response = render(
            request, "ui/partials/_article_add_success.html", {"article": article}
        )
        response["HX-Trigger"] = "article-added"
        return response

    if created:
        messages.success(request, f"Added “{article.title or article.url}”.")
    else:
        messages.info(request, "That article is already in your library.")
    return redirect("ui:article_list")


@login_required
def article_detail(request, article_id: UUID):
    article = get_object_or_404(Article, id=article_id, owner=request.user)
    content_preview = strip_tags(article.content)[:CONTENT_PREVIEW_LENGTH].strip()
    context = {"article": article, "content_preview": content_preview}
    return render(request, "ui/article_detail.html", context)


@login_required
@require_http_methods(["DELETE"])
def article_delete(request, article_id: UUID):
    get_object_or_404(Article, id=article_id, owner=request.user).delete()
    return HttpResponse(status=200)


@login_required
def article_status(request, article_id: UUID):
    article = get_object_or_404(Article, id=article_id, owner=request.user)
    return render(request, "ui/partials/_status_badge.html", {"article": article})
