from collections import defaultdict
from datetime import timedelta
from http import HTTPStatus

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest
from django.utils import timezone
from ninja import Router
from ninja.responses import Response

from ask.helpers.validate_key import validate_and_update_config
from ask.models import AskRequest, PageEmbedding
from ask.models_catalog import get_default_model, get_models_for_provider
from core.authentication import session_auth, token_auth
from pages.models import Page
from users.constants import OrgMemberRole
from users.models import AIProviderConfig, Org, OrgMember
from ninja import Query

from users.schemas import (
    AIModelsListOut,
    AIProviderAvailableOut,
    AIProviderConfigIn,
    AIProviderConfigOut,
    AIProviderConfigUpdateIn,
    AIProviderSummaryOut,
    AIUsageOut,
    IndexingStatusOut,
    IndexingTriggerOut,
    UsageQueryParams,
    ValidationResultOut,
)


ai_router = Router(auth=[token_auth, session_auth])


@ai_router.get("/providers/", response=list[AIProviderConfigOut])
def list_user_ai_providers(request: HttpRequest):
    """List user's personal AI provider configurations."""
    configs = AIProviderConfig.objects.get_for_user(request.user)
    return list(configs)


@ai_router.get("/providers/available/", response=list[AIProviderAvailableOut])
def list_available_providers(request: HttpRequest):
    """List all available AI providers for the user (user's + org's enabled configs)."""
    configs = AIProviderConfig.objects.get_available_for_user(request.user)
    return configs


@ai_router.get("/models/{provider}/", response=AIModelsListOut)
def list_provider_models(request: HttpRequest, provider: str):
    """List available models for a specific provider."""
    models = get_models_for_provider(provider)
    default = get_default_model(provider)
    return {
        "provider": provider,
        "models": models,
        "default_model": default,
    }


@ai_router.post("/providers/", response={201: AIProviderConfigOut, 400: dict})
def create_user_ai_provider(request: HttpRequest, payload: AIProviderConfigIn):
    """Create a new AI provider configuration for the user."""
    config = AIProviderConfig(
        user=request.user,
        provider=payload.provider,
        display_name=payload.display_name or "",
        api_key=payload.api_key or "",
        api_base_url=payload.api_base_url or "",
        model_name=payload.model_name or "",
        is_enabled=payload.is_enabled,
        is_default=payload.is_default,
    )
    config.save()

    if config.api_key:
        is_valid, error = validate_and_update_config(config)
        if not is_valid:
            return Response(
                {
                    "message": f"API key validation failed: {error}",
                    "config": AIProviderConfigOut.from_orm(config).dict(),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

    return 201, config


@ai_router.get("/providers/{config_id}/", response={200: AIProviderConfigOut, 404: dict})
def get_user_ai_provider(request: HttpRequest, config_id: str):
    """Get a specific AI provider configuration."""
    config = AIProviderConfig.objects.filter(user=request.user, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)
    return config


@ai_router.patch("/providers/{config_id}/", response={200: AIProviderConfigOut, 400: dict, 404: dict})
def update_user_ai_provider(request: HttpRequest, config_id: str, payload: AIProviderConfigUpdateIn):
    """Update an AI provider configuration."""
    config = AIProviderConfig.objects.filter(user=request.user, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)

    update_fields = []
    key_changed = False

    if payload.display_name is not None:
        config.display_name = payload.display_name
        update_fields.append("display_name")

    if payload.api_key is not None:
        config.api_key = payload.api_key
        update_fields.append("api_key")
        key_changed = True
        config.is_validated = False
        update_fields.append("is_validated")

    if payload.api_base_url is not None:
        config.api_base_url = payload.api_base_url
        update_fields.append("api_base_url")
        key_changed = True

    if payload.model_name is not None:
        config.model_name = payload.model_name
        update_fields.append("model_name")

    if payload.is_enabled is not None:
        config.is_enabled = payload.is_enabled
        update_fields.append("is_enabled")

    if payload.is_default is not None:
        config.is_default = payload.is_default
        update_fields.append("is_default")

    if update_fields:
        config.save()

    if key_changed and config.api_key:
        is_valid, error = validate_and_update_config(config)
        if not is_valid:
            return Response(
                {
                    "message": f"API key validation failed: {error}",
                    "config": AIProviderConfigOut.from_orm(config).dict(),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

    return config


@ai_router.delete("/providers/{config_id}/", response={204: None, 404: dict})
def delete_user_ai_provider(request: HttpRequest, config_id: str):
    """Delete an AI provider configuration."""
    config = AIProviderConfig.objects.filter(user=request.user, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)
    config.delete()
    return 204, None


@ai_router.post("/providers/{config_id}/validate/", response={200: ValidationResultOut, 404: dict})
def validate_user_ai_provider(request: HttpRequest, config_id: str):
    """Manually validate an AI provider configuration."""
    config = AIProviderConfig.objects.filter(user=request.user, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)

    is_valid, error = validate_and_update_config(config)
    return {"is_valid": is_valid, "error": error}


@ai_router.get("/orgs/{org_id}/providers/", response={200: list[AIProviderConfigOut], 403: dict, 404: dict})
def list_org_ai_providers(request: HttpRequest, org_id: str):
    """List organization's AI provider configurations (admin only)."""
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    configs = AIProviderConfig.objects.get_for_org(org)
    return 200, list(configs)


@ai_router.get("/orgs/{org_id}/providers/summary/", response={200: list[AIProviderSummaryOut], 403: dict, 404: dict})
def list_org_ai_providers_summary(request: HttpRequest, org_id: str):
    """List organization's AI providers (read-only summary for any member).

    This endpoint is accessible to all org members, not just admins.
    It returns only non-sensitive information: provider type, display name,
    and enabled/validated status. No API keys, base URLs, or model configs.
    """
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership:
        return Response({"message": "Not a member of this organization"}, status=HTTPStatus.FORBIDDEN)

    configs = AIProviderConfig.objects.filter(org=org)
    return 200, list(configs)


@ai_router.post("/orgs/{org_id}/providers/", response={201: AIProviderConfigOut, 400: dict, 403: dict, 404: dict})
def create_org_ai_provider(request: HttpRequest, org_id: str, payload: AIProviderConfigIn):
    """Create an AI provider configuration for the organization (admin only)."""
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    config = AIProviderConfig(
        org=org,
        provider=payload.provider,
        display_name=payload.display_name or "",
        api_key=payload.api_key or "",
        api_base_url=payload.api_base_url or "",
        model_name=payload.model_name or "",
        is_enabled=payload.is_enabled,
        is_default=payload.is_default,
    )
    config.save()

    if config.api_key:
        is_valid, error = validate_and_update_config(config)
        if not is_valid:
            return Response(
                {
                    "message": f"API key validation failed: {error}",
                    "config": AIProviderConfigOut.from_orm(config).dict(),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

    return 201, config


@ai_router.patch(
    "/orgs/{org_id}/providers/{config_id}/",
    response={200: AIProviderConfigOut, 400: dict, 403: dict, 404: dict},
)
def update_org_ai_provider(request: HttpRequest, org_id: str, config_id: str, payload: AIProviderConfigUpdateIn):
    """Update an organization's AI provider configuration (admin only)."""
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    config = AIProviderConfig.objects.filter(org=org, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)

    update_fields = []
    key_changed = False

    if payload.display_name is not None:
        config.display_name = payload.display_name
        update_fields.append("display_name")

    if payload.api_key is not None:
        config.api_key = payload.api_key
        update_fields.append("api_key")
        key_changed = True
        config.is_validated = False
        update_fields.append("is_validated")

    if payload.api_base_url is not None:
        config.api_base_url = payload.api_base_url
        update_fields.append("api_base_url")
        key_changed = True

    if payload.model_name is not None:
        config.model_name = payload.model_name
        update_fields.append("model_name")

    if payload.is_enabled is not None:
        config.is_enabled = payload.is_enabled
        update_fields.append("is_enabled")

    if payload.is_default is not None:
        config.is_default = payload.is_default
        update_fields.append("is_default")

    if update_fields:
        config.save()

    if key_changed and config.api_key:
        is_valid, error = validate_and_update_config(config)
        if not is_valid:
            return Response(
                {
                    "message": f"API key validation failed: {error}",
                    "config": AIProviderConfigOut.from_orm(config).dict(),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

    return config


@ai_router.delete("/orgs/{org_id}/providers/{config_id}/", response={204: None, 403: dict, 404: dict})
def delete_org_ai_provider(request: HttpRequest, org_id: str, config_id: str):
    """Delete an organization's AI provider configuration (admin only)."""
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    config = AIProviderConfig.objects.filter(org=org, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)

    config.delete()
    return 204, None


@ai_router.post(
    "/orgs/{org_id}/providers/{config_id}/validate/", response={200: ValidationResultOut, 403: dict, 404: dict}
)
def validate_org_ai_provider(request: HttpRequest, org_id: str, config_id: str):
    """Manually validate an organization's AI provider configuration (admin only)."""
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    config = AIProviderConfig.objects.filter(org=org, external_id=config_id).first()
    if not config:
        return Response({"message": "Configuration not found"}, status=HTTPStatus.NOT_FOUND)

    is_valid, error = validate_and_update_config(config)
    return {"is_valid": is_valid, "error": error}


def _aggregate_usage(queryset, days=30, tz_offset_minutes=0):
    """Aggregate usage statistics from AskRequest queryset.

    Args:
        tz_offset_minutes: Client timezone offset in minutes (e.g., -480 for PST).
                          Positive = behind UTC, negative = ahead of UTC.
    """
    from datetime import timezone as dt_timezone

    client_tz = dt_timezone(timedelta(minutes=-tz_offset_minutes))

    cutoff = timezone.now() - timedelta(days=days)
    recent = queryset.filter(asked__gte=cutoff, status="ok")

    total_requests = recent.count()

    total_tokens = 0
    by_provider = defaultdict(int)

    for req in recent:
        provider = req.provider
        by_provider[provider] += 1
        usage = req.details.get("usage", {})
        total_tokens += usage.get("total_tokens", 0)

    daily_by_provider = (
        recent.annotate(date=TruncDate("asked", tzinfo=client_tz))
        .values("date", "provider")
        .annotate(requests=Count("id"))
        .order_by("date", "provider")
    )

    daily_map = defaultdict(lambda: {"requests": 0, "by_provider": {}})
    for entry in daily_by_provider:
        date_str = entry["date"].isoformat() if entry["date"] else None
        if date_str:
            daily_map[date_str]["requests"] += entry["requests"]
            daily_map[date_str]["by_provider"][entry["provider"]] = entry["requests"]

    daily = [
        {"date": date_str, "requests": data["requests"], "by_provider": data["by_provider"]}
        for date_str, data in sorted(daily_map.items())
    ]

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "by_provider": dict(by_provider),
        "daily": daily,
    }


@ai_router.get("/usage/", response=AIUsageOut)
def get_user_usage(request: HttpRequest, query: UsageQueryParams = Query(...)):
    """Get AI usage statistics for the current user's personal API keys.

    Only includes requests that used user-level AI provider configs.

    Query params:
        tz_offset: Client timezone offset in minutes from UTC (e.g., -480 for PST).
    """
    user_config_ids = AIProviderConfig.objects.filter(user=request.user).values_list("id", flat=True)
    queryset = AskRequest.objects.filter(ai_config_id__in=user_config_ids)
    return _aggregate_usage(queryset, tz_offset_minutes=query.tz_offset)


@ai_router.get("/orgs/{org_id}/usage/", response={200: AIUsageOut, 403: dict, 404: dict})
def get_org_usage(request: HttpRequest, org_id: str, query: UsageQueryParams = Query(...)):
    """Get AI usage statistics for the organization (admin only).

    Only includes requests that used org-level AI provider configs.

    Query params:
        tz_offset: Client timezone offset in minutes from UTC (e.g., -480 for PST).
    """
    org = Org.objects.filter(external_id=org_id).first()
    if not org:
        return Response({"message": "Organization not found"}, status=HTTPStatus.NOT_FOUND)

    membership = OrgMember.objects.filter(org=org, user=request.user).first()
    if not membership or membership.role != OrgMemberRole.ADMIN.value:
        return Response({"message": "Admin access required"}, status=HTTPStatus.FORBIDDEN)

    org_config_ids = AIProviderConfig.objects.filter(org=org).values_list("id", flat=True)
    queryset = AskRequest.objects.filter(ai_config_id__in=org_config_ids)
    return 200, _aggregate_usage(queryset, tz_offset_minutes=query.tz_offset)


@ai_router.get("/indexing/status/", response=IndexingStatusOut)
def get_indexing_status(request: HttpRequest):
    """Get the indexing status for the user's pages."""
    user_pages = Page.objects.get_user_editable_pages(request.user).filter(is_deleted=False)
    total_pages = user_pages.count()

    indexed_page_ids = set(PageEmbedding.objects.filter(page__in=user_pages).values_list("page_id", flat=True))
    indexed_pages = len(indexed_page_ids)
    pending_pages = total_pages - indexed_pages

    has_valid_provider = bool(AIProviderConfig.objects.get_available_for_user(request.user))

    return {
        "total_pages": total_pages,
        "indexed_pages": indexed_pages,
        "pending_pages": pending_pages,
        "has_valid_provider": has_valid_provider,
    }


@ai_router.post("/indexing/trigger/", response={200: IndexingTriggerOut, 400: dict})
def trigger_indexing(request: HttpRequest):
    """Trigger indexing of all unindexed pages for the user."""
    from ask.tasks import index_user_pages

    available_providers = AIProviderConfig.objects.get_available_for_user(request.user)
    if not available_providers:
        return Response(
            {"message": "No valid AI provider configured. Please add an API key in Settings."},
            status=HTTPStatus.BAD_REQUEST,
        )

    user_pages = Page.objects.get_user_editable_pages(request.user).filter(is_deleted=False)
    indexed_page_ids = set(PageEmbedding.objects.filter(page__in=user_pages).values_list("page_id", flat=True))
    pending_page_ids = list(user_pages.exclude(id__in=indexed_page_ids).values_list("external_id", flat=True))

    if not pending_page_ids:
        return {"triggered": False, "pages_queued": 0, "message": "All pages are already indexed."}

    index_user_pages.delay(request.user.id, pending_page_ids)

    return {
        "triggered": True,
        "pages_queued": len(pending_page_ids),
        "message": f"Indexing {len(pending_page_ids)} pages in the background.",
    }
