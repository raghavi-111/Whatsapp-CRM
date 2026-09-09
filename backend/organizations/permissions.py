from .models import OrganizationMember


def get_current_membership(user):
    if not user or not user.is_authenticated:
        return None
    return (
        OrganizationMember.objects.select_related("organization", "user")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )


def get_current_organization(user):
    membership = get_current_membership(user)
    return membership.organization if membership else None


def is_owner(membership):
    return bool(membership and membership.role == OrganizationMember.ROLE_OWNER)


def is_admin(membership):
    return bool(membership and membership.role == OrganizationMember.ROLE_ADMIN)


def can_manage_team(membership):
    return is_owner(membership) or is_admin(membership)


def can_manage_settings(membership):
    return can_manage_team(membership)


def can_invite_role(membership, role):
    if is_owner(membership):
        return role in [OrganizationMember.ROLE_ADMIN, OrganizationMember.ROLE_AGENT]
    if is_admin(membership):
        return role == OrganizationMember.ROLE_AGENT
    return False


def can_manage_member(actor_membership, target_membership):
    if not actor_membership or not target_membership:
        return False
    if actor_membership.organization_id != target_membership.organization_id:
        return False
    if is_owner(actor_membership):
        return True
    if is_admin(actor_membership):
        return target_membership.role == OrganizationMember.ROLE_AGENT
    return False


def active_owner_count(organization):
    return OrganizationMember.objects.filter(
        organization=organization,
        role=OrganizationMember.ROLE_OWNER,
        status=OrganizationMember.STATUS_ACTIVE,
    ).count()
