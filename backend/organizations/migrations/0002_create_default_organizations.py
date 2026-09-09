from django.conf import settings
from django.db import migrations
from django.utils.text import slugify


def unique_slug_for(Organization, name):
    base_slug = slugify(name) or "organization"
    slug = base_slug
    counter = 2

    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def create_default_organizations(apps, schema_editor):
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app_label, user_model_name)
    Organization = apps.get_model("organizations", "Organization")
    OrganizationMember = apps.get_model("organizations", "OrganizationMember")

    for user in User.objects.all():
        if OrganizationMember.objects.filter(user=user, status="active").exists():
            continue

        organization_name = f"{user.email}'s Organization"
        organization = Organization.objects.create(
            name=organization_name,
            slug=unique_slug_for(Organization, organization_name),
            owner=user,
        )
        OrganizationMember.objects.create(
            organization=organization,
            user=user,
            role="owner",
            status="active",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_organizations, migrations.RunPython.noop),
    ]
