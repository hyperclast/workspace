from django.contrib import admin

from .models import Update


@admin.register(Update)
class UpdateAdmin(admin.ModelAdmin):
    list_display = ["title", "is_published", "published_at", "emailed_at", "spam_score", "created_at"]
    list_filter = ["is_published", "created_at"]
    search_fields = ["title", "slug", "content"]
    readonly_fields = ["slug", "emailed_at", "spam_score", "spam_rules", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    def get_fieldsets(self, request, obj=None):
        if obj:
            return [
                (None, {"fields": ["title", "slug", "content", "image_url"]}),
                ("Publishing", {"fields": ["is_published", "published_at"]}),
                ("Email Status", {"fields": ["emailed_at"], "classes": ["collapse"]}),
                ("Spam Analysis", {"fields": ["spam_score", "spam_rules"], "classes": ["collapse"]}),
                ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
            ]
        return [
            (None, {"fields": ["title", "content", "image_url"]}),
            ("Publishing", {"fields": ["is_published", "published_at"]}),
        ]
