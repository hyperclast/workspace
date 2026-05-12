from django.contrib import admin
from django.db.models import Sum

from ask.models import EmbeddingUsage


@admin.register(EmbeddingUsage)
class EmbeddingUsageAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "user",
        "page",
        "model",
        "kind",
        "key_source",
        "total_tokens",
        "cost_usd",
    )
    list_filter = ("kind", "key_source", "model")
    search_fields = (
        "user__email",
        "user__username",
        "page__external_id",
        "page__title",
        "model",
    )
    readonly_fields = ("created", "modified")
    date_hierarchy = "created"
    ordering = ("-created",)
    list_select_related = ("user", "page")

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response

        totals = qs.aggregate(total_cost=Sum("cost_usd"), total_tokens=Sum("total_tokens"))
        response.context_data["summary_total_cost"] = totals.get("total_cost") or 0
        response.context_data["summary_total_tokens"] = totals.get("total_tokens") or 0
        return response
