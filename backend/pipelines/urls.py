from django.urls import path

from .views import DealDetailView, DealListCreateView


urlpatterns = [
    path("deals/", DealListCreateView.as_view(), name="deal-list-create"),
    path("deals/<int:deal_id>/", DealDetailView.as_view(), name="deal-detail"),
]
