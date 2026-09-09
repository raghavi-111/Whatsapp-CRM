from django.urls import path

from .views import (
    CurrentOrganizationView,
    OrganizationInvitationAcceptView,
    OrganizationInvitationCancelView,
    OrganizationInvitationPublicView,
    OrganizationInvitationsView,
    OrganizationListCreateView,
    OrganizationMemberDetailView,
    OrganizationMembersView,
)


urlpatterns = [
    path("", OrganizationListCreateView.as_view(), name="organization-list-create"),
    path("current/", CurrentOrganizationView.as_view(), name="organization-current"),
    path("members/", OrganizationMembersView.as_view(), name="organization-members"),
    path("members/<int:member_id>/", OrganizationMemberDetailView.as_view(), name="organization-member-detail"),
    path("invitations/", OrganizationInvitationsView.as_view(), name="organization-invitations"),
    path("invitations/<int:invitation_id>/cancel/", OrganizationInvitationCancelView.as_view(), name="organization-invitation-cancel"),
    path("invitations/<str:token>/", OrganizationInvitationPublicView.as_view(), name="organization-invitation-public"),
    path("invitations/<str:token>/accept/", OrganizationInvitationAcceptView.as_view(), name="organization-invitation-accept"),
]
