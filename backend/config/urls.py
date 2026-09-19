from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from automations.views import MediaListView, MediaUploadView


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "message": "Backend is running"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/auth/", include("accounts.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/contacts/", include("contacts.urls")),
    path("api/conversations/", include("conversations.urls")),
    path("api/whatsapp/", include("whatsapp.urls")),
    path("api/templates/", include("templates.urls")),
    path("api/automations/", include("automations.urls")),
    path("api/media/", MediaListView.as_view(), name="media-list"),
    path("api/media/upload/", MediaUploadView.as_view(), name="media-upload"),
    path("api/flows/", include("flows.urls")),
    path("api/pipelines/", include("pipelines.urls")),
    path("api/leads/", include("leads.urls")),
    path("api/broadcasts/", include("broadcasts.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/tags/", include("support.urls")),
    path("api/lead-collector/", include("lead_collector.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
