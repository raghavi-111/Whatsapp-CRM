from django.urls import path

from .views import (
    AgentsAnalyticsView,
    AutomationsAnalyticsView,
    ConversationsAnalyticsView,
    MessagesAnalyticsView,
    SummaryAnalyticsView,
)


urlpatterns = [
    path("summary/", SummaryAnalyticsView.as_view(), name="analytics-summary"),
    path("messages/", MessagesAnalyticsView.as_view(), name="analytics-messages"),
    path("conversations/", ConversationsAnalyticsView.as_view(), name="analytics-conversations"),
    path("agents/", AgentsAnalyticsView.as_view(), name="analytics-agents"),
    path("automations/", AutomationsAnalyticsView.as_view(), name="analytics-automations"),
]
