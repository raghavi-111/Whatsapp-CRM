from django.urls import path

from .views import TagDetailView, TagListCreateView


urlpatterns = [
    path("", TagListCreateView.as_view(), name="tag-list-create"),
    path("<int:tag_id>/", TagDetailView.as_view(), name="tag-detail"),
]
