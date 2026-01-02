from django.contrib import admin
from django.utils.html import format_html

from .models import Page, PageEditor, Project


class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    fields = ["title", "external_id", "creator", "is_deleted", "updated"]
    readonly_fields = ["external_id", "updated"]
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "org", "creator", "page_count", "is_deleted", "created"]
    list_filter = ["is_deleted", "created", "org"]
    search_fields = ["name", "external_id", "org__name", "creator__email"]
    readonly_fields = ["external_id", "created", "modified"]
    autocomplete_fields = ["org", "creator"]
    date_hierarchy = "created"
    list_select_related = ["org", "creator"]
    inlines = [PageInline]

    def page_count(self, obj):
        return obj.pages.filter(is_deleted=False).count()

    page_count.short_description = "Pages"


class PageEditorInline(admin.TabularInline):
    model = PageEditor
    extra = 0
    autocomplete_fields = ["user"]
    readonly_fields = ["created"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "project_link", "creator", "editor_count", "is_deleted", "updated"]
    list_filter = ["is_deleted", "created", "project__org"]
    search_fields = ["title", "external_id", "creator__email", "project__name"]
    readonly_fields = ["external_id", "created", "modified", "updated"]
    autocomplete_fields = ["project", "creator"]
    date_hierarchy = "created"
    list_select_related = ["project", "creator"]
    inlines = [PageEditorInline]

    def project_link(self, obj):
        if obj.project:
            url = f"/admin/pages/project/{obj.project.pk}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.project.name)
        return "-"

    project_link.short_description = "Project"

    def editor_count(self, obj):
        return obj.editors.count()

    editor_count.short_description = "Editors"


@admin.register(PageEditor)
class PageEditorAdmin(admin.ModelAdmin):
    list_display = ["page", "user", "created"]
    list_filter = ["created"]
    search_fields = ["page__title", "user__email"]
    autocomplete_fields = ["page", "user"]
    readonly_fields = ["created"]
