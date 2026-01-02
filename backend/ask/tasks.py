from typing import List

from django.conf import settings

from ask.models import PageEmbedding
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

    log_info("Starting bulk indexing of %d pages for user %s", len(page_external_ids), user_id)

    indexed = 0
    failed = 0

    for page_id in page_external_ids:
        try:
            page = Page.objects.get(external_id=page_id)
            _, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
            log_info("Bulk index: %s embedding for %s", action, page_id)
            indexed += 1
        except Exception as e:
            log_error("Bulk index: error for page %s: %s", page_id, e)
            failed += 1

    log_info(
        "Bulk indexing complete for user %s: %d indexed, %d failed",
        user_id,
        indexed,
        failed,
    )
