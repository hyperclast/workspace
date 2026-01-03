from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import reverse
from django.utils.html import format_html

from .forms import ProfileAdminForm
from .models import Org, OrgMember, PersonalEmailDomain, Profile, StripeLog

admin.site.site_header = "Hyperclast Admin"
admin.site.site_title = "Hyperclast"
admin.site.index_title = "Administration"


class OrgMemberInline(admin.TabularInline):
    model = OrgMember
    extra = 0
    autocomplete_fields = ["user"]
    readonly_fields = ["created"]


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ["name", "domain", "external_id", "member_count", "created"]
    list_filter = ["created"]
    search_fields = ["name", "domain", "external_id"]
    readonly_fields = ["external_id", "created", "modified"]
    date_hierarchy = "created"
    inlines = [OrgMemberInline]

    def member_count(self, obj):
        return obj.members.count()

    member_count.short_description = "Members"


@admin.register(OrgMember)
class OrgMemberAdmin(admin.ModelAdmin):
    list_display = ["org", "user", "role", "created"]
    list_filter = ["role", "created"]
    search_fields = ["org__name", "user__email"]
    autocomplete_fields = ["org", "user"]
    readonly_fields = ["created"]
    list_select_related = ["org", "user"]


@admin.register(get_user_model())
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = [
        "email",
        "username",
        "first_name",
        "last_name",
        "date_joined",
        "profile_link",
    ]
    list_display_links = ["email"]
    search_fields = ["email", "username", "first_name", "last_name"]
    date_hierarchy = "date_joined"

    def profile_link(self, obj):
        if hasattr(obj, "profile") and obj.profile is not None:
            url = reverse("admin:users_profile_change", args=[obj.profile.pk])
            return format_html('<a href="{}">Edit Profile</a>', url)
        return "-"

    profile_link.short_description = "Profile"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ["user", "receive_product_updates", "last_active", "tz", "created"]
    list_filter = ["receive_product_updates"]
    search_fields = ["user__email"]
    readonly_fields = ["created", "modified", "access_token"]


@admin.register(StripeLog)
class StripeLogAdmin(admin.ModelAdmin):
    list_display = ["event", "email", "user", "created"]
    list_filter = ["event", "created"]
    search_fields = ["event", "email", "user__email"]
    readonly_fields = ["event", "email", "user", "payload_pretty", "created", "modified"]
    exclude = ["payload"]
    date_hierarchy = "created"
    ordering = ["-created"]

    @admin.display(description="Payload")
    def payload_pretty(self, obj):
        import json

        formatted = json.dumps(obj.payload, indent=2, sort_keys=True)
        return format_html('<pre style="margin:0; white-space:pre-wrap; word-wrap:break-word;">{}</pre>', formatted)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PersonalEmailDomain)
class PersonalEmailDomainAdmin(admin.ModelAdmin):
    list_display = ["substring", "created"]
    search_fields = ["substring"]
    readonly_fields = ["created", "modified"]
    ordering = ["substring"]
