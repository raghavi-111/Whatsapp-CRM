from django.urls import path

from .views import (
    AutomationLogListView,
    AutomationMediaListCreateView,
    AutomationRuleDetailView,
    AutomationRuleListCreateView,
    AutomationSimulateInboundMessageView,
)


urlpatterns = [
    path("", AutomationRuleListCreateView.as_view(), name="automation-list-create"),
    path("logs/", AutomationLogListView.as_view(), name="automation-logs"),
    path("media/", AutomationMediaListCreateView.as_view(), name="automation-media"),
    path("simulate-inbound/", AutomationSimulateInboundMessageView.as_view(), name="automation-simulate-inbound"),
    path("<int:rule_id>/", AutomationRuleDetailView.as_view(), name="automation-detail"),
]
