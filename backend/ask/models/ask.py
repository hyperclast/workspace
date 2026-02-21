import uuid
from typing import List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel
from litellm.exceptions import APIError

from ask.constants import AIProvider, AskRequestError, AskRequestStatus
from ask.exceptions import AIKeyNotConfiguredError
from ask.helpers import build_ask_request_messages, compute_embedding, create_chat_completion, parse_mentions
from ask.schemas import AskOut, PageReference
from backend.utils import log_error, log_info, log_warning
from pages.models import Page

from .embeddings import PageEmbedding


User = get_user_model()


class AskRequestManager(models.Manager):
    def process_query(
        self,
        query: str,
        user,
        page_ids: Optional[List[str]] = None,
        provider: Optional[str] = None,
        config_id: Optional[str] = None,
        model: Optional[str] = None,
    ):
        ask_request = self.create(
            user=user,
            query=query,
        )

        try:
            question, mentions = parse_mentions(query=query)

            if not question:
                ask_request.mark_as_failed(AskRequestError.EMPTY_QUESTION.value)
                return ask_request

            pages = []
            limit = settings.ASK_EMBEDDINGS_MAX_PAGES

            # Merge page_ids (from API) and mentions (from query) with prioritization
            # page_ids take priority over mentions
            page_ids = page_ids or []
            priority_page_ids = []
            seen = set()

            # Add page_ids first (higher priority)
            for nid in page_ids:
                if nid not in seen:
                    priority_page_ids.append(nid)
                    seen.add(nid)

            # Add mentions second (lower priority)
            for nid in mentions:
                if nid not in seen:
                    priority_page_ids.append(nid)
                    seen.add(nid)

            # Apply limit to the merged list
            priority_page_ids = priority_page_ids[:limit]

            # If we have priority pages, retrieve them directly
            if priority_page_ids:
                pages = list(Page.objects.get_user_accessible_pages(user).filter(external_id__in=priority_page_ids))
            # Otherwise, use similarity search
            else:
                input_embedding = compute_embedding(question, user=user)
                search_page_ids = list(
                    PageEmbedding.objects.similarity_search(
                        user=user, input_embedding=input_embedding, limit=limit
                    ).values_list("page__external_id", flat=True)
                )
                pages = list(Page.objects.get_user_accessible_pages(user).filter(external_id__in=search_page_ids))

            if not pages:
                ask_request.mark_as_failed(AskRequestError.NO_MATCHING_PAGES.value)
                return ask_request

            messages = build_ask_request_messages(question, pages)

            from ask.helpers.llm import get_ai_config_for_user

            resolved_config = None
            resolved_provider = provider
            try:
                resolved_config = get_ai_config_for_user(user, provider=provider, config_id=config_id)
                resolved_provider = resolved_config.provider
            except Exception:
                pass

            response = create_chat_completion(
                messages=messages,
                user=user,
                provider=provider,
                config_id=config_id,
                model=model,
            )
            answer = response["choices"][0]["message"]["content"]

            page_references = [
                PageReference(
                    external_id=str(n.external_id),
                    title=n.title,
                    updated=n.updated,
                    created=n.created,
                    modified=n.modified,
                )
                for n in pages
            ]
            ask_out = AskOut(answer=answer, pages=page_references)
            results = ask_out.dict()

            ask_request.answer = answer
            ask_request.results = results
            ask_request.replied = timezone.now()
            ask_request.details = response
            ask_request.status = AskRequestStatus.OK.value
            if resolved_provider:
                ask_request.provider = resolved_provider
            if resolved_config:
                ask_request.ai_config = resolved_config
            ask_request.save()

        except AIKeyNotConfiguredError as e:
            log_error("AI key not configured for user %s: %s", user, e)
            ask_request.error = "ai_key_not_configured"
            ask_request.status = AskRequestStatus.FAILED.value
            ask_request.save(update_fields=["status", "error", "modified"])

        except Exception as e:
            log_error("Error processing query %s from user %s: %s", ask_request, user, e)
            error = AskRequestError.API_ERROR.value if isinstance(e, APIError) else AskRequestError.UNEXPECTED.value
            ask_request.mark_as_failed(error)

        return ask_request


class AskRequest(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="ask_requests",
        null=True,
        default=None,
    )
    ai_config = models.ForeignKey(
        "users.AIProviderConfig",
        on_delete=models.SET_NULL,
        related_name="ask_requests",
        null=True,
        blank=True,
        default=None,
    )
    external_id = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
    )
    query = models.TextField()
    asked = models.DateTimeField(
        db_index=True,
        default=timezone.now,
    )
    answer = models.TextField(
        blank=True,
        null=True,
        default=None,
    )
    results = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
    )
    replied = models.DateTimeField(
        db_index=True,
        null=True,
        default=None,
    )
    status = models.TextField(
        db_index=True,
        choices=AskRequestStatus.choices,
        default=AskRequestStatus.PENDING.value,
    )
    provider = models.TextField(
        db_index=True,
        choices=AIProvider.choices,
        default=AIProvider.OPENAI.value,
    )
    error = models.TextField(
        db_index=True,
        blank=True,
        default="",
    )
    details = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
    )

    objects = AskRequestManager()

    def __str__(self):
        return str(self.external_id)

    @property
    def is_pending(self) -> bool:
        return self.status == AskRequestStatus.PENDING.value

    @property
    def is_ok(self) -> bool:
        return self.status == AskRequestStatus.OK.value

    @property
    def is_failed(self) -> bool:
        return self.status == AskRequestStatus.FAILED.value

    def mark_as_pending(self):
        self.status = AskRequestStatus.PENDING.value
        self.error = ""
        self.save(update_fields=["status", "error", "modified"])

    def mark_as_ok(self):
        self.status = AskRequestStatus.OK.value
        self.error = ""
        self.save(update_fields=["status", "error", "modified"])

    def mark_as_failed(self, error: Optional[str] = ""):
        self.status = AskRequestStatus.FAILED.value
        self.error = error
        self.save(update_fields=["status", "error", "modified"])
