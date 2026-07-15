import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIMENSIONS = 768


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name=_("owner"),
    )
    name = models.CharField(max_length=100, verbose_name=_("name"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="unique_owner_tag_name"
            )
        ]
        ordering = ["name"]
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        FETCHING = "fetching", _("Fetching")
        ENRICHED = "enriched", _("Enriched")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name=_("owner"),
    )
    url = models.URLField(max_length=2048, verbose_name=_("URL"))
    url_hash = models.CharField(max_length=64, editable=False)
    title = models.CharField(max_length=512, blank=True, verbose_name=_("title"))
    content = models.TextField(blank=True, verbose_name=_("content"))
    summary = models.TextField(blank=True, verbose_name=_("summary"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("status"),
    )
    tags = models.ManyToManyField(
        Tag,
        related_name="articles",
        blank=True,
        db_table="article_tags",
        verbose_name=_("tags"),
    )
    fetched_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("fetched at")
    )
    embedding = VectorField(
        dimensions=EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
        verbose_name=_("embedding"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "url_hash"], name="unique_owner_url_hash"
            )
        ]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            HnswIndex(
                name="article_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
        ordering = ["-created_at"]
        verbose_name = _("article")
        verbose_name_plural = _("articles")

    def __str__(self) -> str:
        return self.title or self.url

    def save(self, *args, **kwargs):
        self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()
        super().save(*args, **kwargs)
