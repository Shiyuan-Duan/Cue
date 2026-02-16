from django.urls import path

from .views import AssistantMessageView, AssistantVoiceTurnView, RefineTaskArtifactView

urlpatterns = [
    path("message", AssistantMessageView.as_view(), name="assistant-message"),
    path("voice-turn", AssistantVoiceTurnView.as_view(), name="assistant-voice-turn"),
    path("tasks/refine", RefineTaskArtifactView.as_view(), name="assistant-task-refine"),
]
