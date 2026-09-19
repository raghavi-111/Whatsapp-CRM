from django.urls import path

from .views import (
    BroadcastCampaignDetailView,
    BroadcastCampaignListCreateView,
    BroadcastCancelView,
    BroadcastEstimateView,
    BroadcastScheduleView,
    BroadcastSendNowView,
)


urlpatterns = [
    path("campaigns/", BroadcastCampaignListCreateView.as_view(), name="broadcast-campaign-list-create"),
    path("campaigns/estimate/", BroadcastEstimateView.as_view(), name="broadcast-campaign-estimate"),
    path("campaigns/<int:campaign_id>/", BroadcastCampaignDetailView.as_view(), name="broadcast-campaign-detail"),
    path("campaigns/<int:campaign_id>/send-now/", BroadcastSendNowView.as_view(), name="broadcast-campaign-send-now"),
    path("campaigns/<int:campaign_id>/schedule/", BroadcastScheduleView.as_view(), name="broadcast-campaign-schedule"),
    path("campaigns/<int:campaign_id>/cancel/", BroadcastCancelView.as_view(), name="broadcast-campaign-cancel"),
]
