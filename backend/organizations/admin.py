from django.contrib import admin

from .models import Organization, OrganizationInvitation, OrganizationMember


class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "created_at")
    search_fields = ("name", "slug", "owner__email")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["owner"]
    inlines = [OrganizationMemberInline]


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("organization__name", "user__email")
    autocomplete_fields = ["organization", "user"]


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "status", "invited_by", "expires_at", "created_at")
    list_filter = ("role", "status", "created_at", "expires_at")
    search_fields = ("email", "organization__name", "token")
    autocomplete_fields = ["organization", "invited_by", "accepted_by"]
    readonly_fields = ("token", "created_at", "accepted_at")
