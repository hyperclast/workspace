from django.contrib import admin
from django.forms import HiddenInput
from django.template.loader import render_to_string

from .models import SentEmail


class SentEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "to_address", "recipient", "status_code", "message_id", "esp_name")
    search_fields = ("subject", "to_address")
    readonly_fields = ("html_content", "text_content", "email_message_preview")

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
