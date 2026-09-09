from django.urls import path

from .views import WhatsAppConfigTestConnectionView, WhatsAppConfigView, WhatsAppSimulateInboundView, WhatsAppWebhookView


urlpatterns = [
    path("config/", WhatsAppConfigView.as_view(), name="whatsapp-config"),
    path("config/test-connection/", WhatsAppConfigTestConnectionView.as_view(), name="whatsapp-config-test-connection"),
    path("webhook/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
    path("simulate-inbound/", WhatsAppSimulateInboundView.as_view(), name="whatsapp-simulate-inbound"),
]
