from django.urls import path

from .views import ContactCategoryListView, ContactDetailView, ContactListCreateView, ContactStartConversationView, ExcelWhatsAppWorkbookView, ExcelWhatsAppSheetView, ExcelWhatsAppPreviewView, ExcelWhatsAppCommitView
from support.views import ContactNotesView, ContactTagsView


urlpatterns = [
    path("", ContactListCreateView.as_view(), name="contact-list-create"),
    path("categories/", ContactCategoryListView.as_view(), name="contact-categories"),
    path("whatsapp-import/workbook/", ExcelWhatsAppWorkbookView.as_view(), name="contact-whatsapp-workbook"),
    path("whatsapp-import/sheet/", ExcelWhatsAppSheetView.as_view(), name="contact-whatsapp-sheet"),
    path("whatsapp-import/preview/", ExcelWhatsAppPreviewView.as_view(), name="contact-whatsapp-preview"),
    path("whatsapp-import/commit/", ExcelWhatsAppCommitView.as_view(), name="contact-whatsapp-commit"),
    path("<int:contact_id>/start-conversation/", ContactStartConversationView.as_view(), name="contact-start-conversation"),
    path("<int:contact_id>/notes/", ContactNotesView.as_view(), name="contact-notes"),
    path("<int:contact_id>/tags/", ContactTagsView.as_view(), name="contact-tags"),
    path("<int:contact_id>/", ContactDetailView.as_view(), name="contact-detail"),
]
