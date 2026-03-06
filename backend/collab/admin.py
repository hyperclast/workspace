from django.contrib import admin

from collab.models import CrdtArchiveBatch


@admin.register(CrdtArchiveBatch)
class CrdtArchiveBatchAdmin(admin.ModelAdmin):
    list_display = ("room_id", "from_update_id", "to_update_id", "row_count", "status", "created")
    list_filter = ("status", "provider")
    search_fields = ("room_id", "object_key")
    readonly_fields = ("external_id", "created", "modified")
    ordering = ("-created",)
