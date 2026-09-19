from django.urls import path

from .views import LeadAssigneeListView, LeadConvertView, LeadDetailView, LeadListCreateView, ServiceDetailView, ServiceListCreateView

urlpatterns = [
    path("", LeadListCreateView.as_view(), name="lead-list-create"),
    path("assignees/", LeadAssigneeListView.as_view(), name="lead-assignees"),
    path("services/", ServiceListCreateView.as_view(), name="service-list-create"),
    path("services/<int:service_id>/", ServiceDetailView.as_view(), name="service-detail"),
    path("<int:lead_id>/", LeadDetailView.as_view(), name="lead-detail"),
    path("<int:lead_id>/convert/", LeadConvertView.as_view(), name="lead-convert"),
]
