from django.urls import path

from .views import ConversationDetailView, ConversationListCreateView, ConversationMediaMessageView, ConversationMessagesView
from support.views import ConversationAssignView, ConversationNotesView, ConversationStatusView


urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("<int:conversation_id>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("<int:conversation_id>/messages/", ConversationMessagesView.as_view(), name="conversation-messages"),
    path("<int:conversation_id>/messages/media/", ConversationMediaMessageView.as_view(), name="conversation-media-message"),
    path("<int:conversation_id>/notes/", ConversationNotesView.as_view(), name="conversation-notes"),
    path("<int:conversation_id>/assign/", ConversationAssignView.as_view(), name="conversation-assign"),
    path("<int:conversation_id>/status/", ConversationStatusView.as_view(), name="conversation-status"),
]
