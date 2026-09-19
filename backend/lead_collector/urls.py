from django.urls import path

from .views import (
    CategoryListView, DecisionMakersView, EnrichBusinessesView, ExcelExportView, ExportView,
    ImportLeadsView, ImportPreviewView, LocationSearchView, ProviderListView,
    SearchDetailView, SearchListCreateView, WhatsAppContactImportView, WhatsAppContactPreviewView,
)

urlpatterns = [
    path("locations/", LocationSearchView.as_view()),
    path("categories/", CategoryListView.as_view()),
    path("providers/", ProviderListView.as_view()),
    path("searches/", SearchListCreateView.as_view()),
    path("searches/<int:search_id>/", SearchDetailView.as_view()),
    path("businesses/enrich/", EnrichBusinessesView.as_view()),
    path("businesses/decision-makers/", DecisionMakersView.as_view()),
    path("exports/csv/", ExportView.as_view()),
    path("exports/excel/", ExcelExportView.as_view()),
    path("imports/preview/", ImportPreviewView.as_view()),
    path("imports/leads/", ImportLeadsView.as_view()),
    path("imports/whatsapp-contacts/preview/", WhatsAppContactPreviewView.as_view()),
    path("imports/whatsapp-contacts/", WhatsAppContactImportView.as_view()),
]
