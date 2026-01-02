from django.contrib import admin
from django.forms import HiddenInput
from django.template.loader import render_to_string

from .models import SentEmail


class SentEmailAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "to_address",
        "email_type",
        "status",
        "spam_score",
        "created",
    )
    list_filter = ("email_type", "status", "created")
    search_fields = ("subject", "to_address", "message_id")
    readonly_fields = (
        "html_content",
        "text_content",
        "email_message_preview",
        "message_id",
        "spam_score",
        "metadata",
        "created",
        "modified",
    )
    date_hierarchy = "created"
    ordering = ["-created"]

    fieldsets = (
        (None, {"fields": ("to_address", "from_address", "subject")}),
        ("Content", {"fields": ("email_message_preview", "text_content"), "classes": ("collapse",)}),
        ("Email Details", {"fields": ("email_type", "status", "esp_name", "message_id")}),
        ("Spam Analysis", {"fields": ("spam_score", "metadata"), "classes": ("collapse",)}),
        ("Relations", {"fields": ("recipient", "related_update"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created", "modified"), "classes": ("collapse",)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and "html_content" in form.base_fields:
            form.base_fields["html_content"].widget = HiddenInput()
        return form

    def email_message_preview(self, obj):
        return render_to_string(
            "core/partials/email-preview.html",
            context={"html_content": obj.html_content},
        )


admin.site.register(SentEmail, SentEmailAdmin)


class VisitSummaryEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "website", "batch_id", "status")
    search_fields = ("subject", "website__domain")
    readonly_fields = ("email_message_preview",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and "body" in form.base_fields:
            form.base_fields["body"].widget = HiddenInput()
        return form

    def email_message_preview(self, obj):
        return render_to_string(
            "core/partials/email-preview.html",
            context={"html_content": obj.body},
        )
