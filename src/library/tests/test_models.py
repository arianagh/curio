import hashlib

import pytest
from django.db import IntegrityError

from library.models import Article, Tag


@pytest.mark.django_db
def test_article_save_computes_url_hash(user):
    article = Article.objects.create(owner=user, url="https://example.com/a")

    assert article.url_hash == hashlib.sha256(b"https://example.com/a").hexdigest()


@pytest.mark.django_db
def test_article_unique_owner_url_hash(user):
    Article.objects.create(owner=user, url="https://example.com/a")

    with pytest.raises(IntegrityError):
        Article.objects.create(owner=user, url="https://example.com/a")


@pytest.mark.django_db
def test_tag_unique_owner_name(user):
    Tag.objects.create(owner=user, name="python")

    with pytest.raises(IntegrityError):
        Tag.objects.create(owner=user, name="python")


@pytest.mark.django_db
def test_article_embedding_defaults_to_none_and_can_be_set(user):
    article = Article.objects.create(owner=user, url="https://example.com/e")
    assert article.embedding is None

    article.embedding = [0.1] * 768
    article.save(update_fields=["embedding"])
    article.refresh_from_db()

    assert list(article.embedding) == pytest.approx([0.1] * 768)
