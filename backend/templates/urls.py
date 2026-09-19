from django.urls import path

from .views import MessageTemplateDetailView, MessageTemplateListCreateView, SendMessageTemplateView


urlpatterns = [
    path("", MessageTemplateListCreateView.as_view(), name="template-list-create"),
    path("<int:template_id>/", MessageTemplateDetailView.as_view(), name="template-detail"),
    path("<int:template_id>/send/", SendMessageTemplateView.as_view(), name="template-send"),
]
