from django.contrib import admin
from django.utils.html import format_html

from .models import ImportAbuseRecord, ImportArchive, ImportBannedUser, ImportedPage, ImportJob


class ImportedPageInline(admin.TabularInline):
    model = ImportedPage
    extra = 0
    fields = ["page", "original_path", "source_hash", "created"]
    readonly_fields = ["created"]
    show_change_link = True
    autocomplete_fields = ["page"]


class ImportArchiveInline(admin.StackedInline):
    model = ImportArchive
    extra = 0
    fields = ["filename", "size_bytes", "content_type", "provider", "bucket", "object_key", "etag"]
    readonly_fields = ["filename", "size_bytes", "content_type", "provider", "bucket", "object_key", "etag"]
    can_delete = False


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = [
        "external_id",
        "user",
        "project_link",
        "provider",
        "status",
        "progress",
        "created",
    ]
    list_filter = ["status", "provider", "created"]
    search_fields = ["external_id", "user__email", "project__name"]
    readonly_fields = [
        "external_id",
        "created",
        "modified",
        "total_pages",
        "pages_imported_count",
        "pages_skipped_count",
        "pages_failed_count",
    ]
    autocomplete_fields = ["user", "project"]
    date_hierarchy = "created"
    list_select_related = ["user", "project"]
    inlines = [ImportArchiveInline, ImportedPageInline]

    def project_link(self, obj):
        if obj.project:
            url = f"/admin/pages/project/{obj.project.pk}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.project.name)
        return "-"

    project_link.short_description = "Project"

    def progress(self, obj):
        if obj.total_pages == 0:
            return "-"
        parts = [f"{obj.pages_imported_count} imported"]
        if obj.pages_skipped_count > 0:
            parts.append(f"{obj.pages_skipped_count} skipped")
        if obj.pages_failed_count > 0:
            parts.append(f"{obj.pages_failed_count} failed")
        return f"{', '.join(parts)} / {obj.total_pages} total"

    progress.short_description = "Progress"


@admin.register(ImportArchive)
class ImportArchiveAdmin(admin.ModelAdmin):
    list_display = ["external_id", "import_job", "filename", "size_display", "provider", "created"]
    list_filter = ["provider", "created"]
    search_fields = ["external_id", "filename", "import_job__external_id"]
    readonly_fields = ["external_id", "created", "modified"]
    date_hierarchy = "created"
    list_select_related = ["import_job"]

    def size_display(self, obj):
        size = obj.size_bytes
        if size is None:
            return "-"
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    size_display.short_description = "Size"


@admin.register(ImportedPage)
class ImportedPageAdmin(admin.ModelAdmin):
    list_display = ["page", "import_job", "source_hash", "original_path", "created"]
    list_filter = ["created"]
    search_fields = ["page__title", "source_hash", "original_path", "import_job__external_id"]
    autocomplete_fields = ["page", "import_job"]
    readonly_fields = ["created", "modified"]
    date_hierarchy = "created"
    list_select_related = ["page", "import_job"]


@admin.register(ImportBannedUser)
class ImportBannedUserAdmin(admin.ModelAdmin):
    list_display = ["user", "enforced", "reason_preview", "created", "modified"]
    list_filter = ["enforced", "created"]
    search_fields = ["user__email", "reason"]
    readonly_fields = ["created", "modified"]
    raw_id_fields = ["user"]
    date_hierarchy = "created"

    def reason_preview(self, obj):
        if obj.reason:
            return obj.reason[:100] + "..." if len(obj.reason) > 100 else obj.reason
        return "-"

    reason_preview.short_description = "Reason"


@admin.register(ImportAbuseRecord)
class ImportAbuseRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "severity", "reason", "ip_address", "created"]
    list_filter = ["severity", "created"]
    search_fields = ["user__email", "reason", "ip_address"]
    readonly_fields = ["created", "modified", "user", "import_job", "details"]
    raw_id_fields = ["user", "import_job"]
    date_hierarchy = "created"
    list_select_related = ["user", "import_job"]
