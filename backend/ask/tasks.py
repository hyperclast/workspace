from typing import List

from django.conf import settings

from ask.helpers.embeddings import collect_embedding_usage, has_embedding_credentials
from ask.models import EmbeddingUsage, PageEmbedding
from backend.utils import log_error, log_info
from core.helpers import task
from pages.models import Page


@task(settings.JOB_AI_QUEUE)
def update_page_embedding(page_id: str, user_id: int = None):
    if not settings.ASK_FEATURE_ENABLED:
        log_info("Skipping embedding compute as ask feature is disabled.")
        return

    try:
        page = Page.objects.get(external_id=page_id)

        user = None
        if user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.filter(id=user_id).first()

        if not user:
            user = page.creator

        if not has_embedding_credentials(user):
            log_info(
                "Skipping embedding for page %s: no embedding credentials available (no server key, no user OpenAI config)",
                page_id,
            )
            return

        _, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)

        log_info("%s page embedding for %s", action, page_id)

    except Exception as e:
        log_error("Error computing page embedding for %s: %s", page_id, e)


@task(settings.JOB_AI_QUEUE)
def index_user_pages(user_id: int, page_external_ids: List[str]):
    """Index multiple pages for a user. Called when user triggers bulk indexing."""
    if not settings.ASK_FEATURE_ENABLED:
        log_info("Skipping bulk indexing as ask feature is disabled.")
        return

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(id=user_id).first()

    if not user:
        log_error("index_user_pages: user %s not found", user_id)
        return

    if not has_embedding_credentials(user):
        log_info(
            "Skipping bulk indexing for user %s: no embedding credentials available",
            user_id,
        )
        return

    log_info("Starting bulk indexing of %d pages for user %s", len(page_external_ids), user_id)

    indexed = 0
    failed = 0

    # Defer audit-row INSERTs to one bulk_create at the end. Each page's
    # PageEmbedding still saves synchronously; only the EmbeddingUsage rows
    # are batched so a many-page run pays one INSERT round-trip instead of N.
    with collect_embedding_usage() as usage_buffer:
        for page_id in page_external_ids:
            try:
                page = Page.objects.get(external_id=page_id)
                _, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
                log_info("Bulk index: %s embedding for %s", action, page_id)
                indexed += 1
            except Exception as e:
                log_error("Bulk index: error for page %s: %s", page_id, e)
                failed += 1

        if usage_buffer:
            try:
                EmbeddingUsage.objects.bulk_create(usage_buffer)
            except Exception as exc:
                log_error(
                    "Bulk EmbeddingUsage flush failed (%s, %d rows): %s",
                    type(exc).__name__,
                    len(usage_buffer),
                    exc,
                )

    log_info(
        "Bulk indexing complete for user %s: %d indexed, %d failed",
        user_id,
        indexed,
        failed,
    )
