from django.conf import settings

from ask.models import PageEmbedding
from backend.utils import log_error, log_info
from core.helpers import task
from pages.models import Page


@task(settings.JOB_AI_QUEUE)
def update_page_embedding(page_id: str):
    if not settings.ASK_FEATURE_ENABLED:
        log_info("Skipping embedding compute ask ask feature is disabled.")
        return

    try:
        page = Page.objects.get(external_id=page_id)
        _, action = PageEmbedding.objects.update_or_create_page_embedding(page)

        log_info("%s page embedding for %s", action, page_id)

    except Exception as e:
        log_error("Error computing page embedding for %s: %s", page_id, e)
