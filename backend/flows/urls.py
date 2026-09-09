from django.urls import path
from .views import FlowDetailView, FlowListCreateView, FlowLogListView, FlowRunCancelView, FlowRunListView, FlowRunRestartView

urlpatterns = [
    path("", FlowListCreateView.as_view()),
    path("runs/", FlowRunListView.as_view()),
    path("runs/<int:pk>/cancel/", FlowRunCancelView.as_view()),
    path("runs/<int:pk>/restart/", FlowRunRestartView.as_view()),
    path("logs/", FlowLogListView.as_view()),
    path("<int:pk>/", FlowDetailView.as_view()),
]
