from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser

from apps.assistant.api.serializers import (
    AssistantMessageRequestSerializer,
    AssistantVoiceTurnRequestSerializer,
    RefineTaskArtifactRequestSerializer,
)
from apps.assistant.models import ConversationSession
from apps.assistant.services import AssistantOrchestrator
from apps.core.services import get_request_user
from apps.tasks.api.serializers import TaskSerializer
from apps.tasks.models import Task


class AssistantMessageView(APIView):
    orchestrator = AssistantOrchestrator()

    def post(self, request):
        serializer = AssistantMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_request_user(request)
        session = None

        session_id = serializer.validated_data.get("session_id")
        if session_id:
            session = ConversationSession.objects.filter(owner=user, id=session_id).first()

        response = self.orchestrator.process_message(
            user=user,
            text=serializer.validated_data["message"],
            session=session,
            user_timezone=serializer.validated_data.get("timezone") or getattr(request, "cue_timezone", None),
        )

        return Response(
            {
                "session_id": response.session_id,
                "reply": response.text,
                "action_cards": response.action_cards,
            }
        )


class AssistantVoiceTurnView(APIView):
    orchestrator = AssistantOrchestrator()
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = AssistantVoiceTurnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_request_user(request)
        session = None
        session_id = serializer.validated_data.get("session_id")
        if session_id:
            session = ConversationSession.objects.filter(owner=user, id=session_id).first()

        result = self.orchestrator.process_voice_turn(
            user=user,
            audio_file=serializer.validated_data["audio"],
            session=session,
            user_timezone=serializer.validated_data.get("timezone") or getattr(request, "cue_timezone", None),
        )
        response = result["response"]
        speech = result.get("speech") or {}
        return Response(
            {
                "session_id": response.session_id,
                "transcript": result["transcript"],
                "reply": response.text,
                "action_cards": response.action_cards,
                "speech_audio_base64": speech.get("audio_base64"),
                "speech_mime_type": speech.get("mime_type"),
            }
        )


class RefineTaskArtifactView(APIView):
    orchestrator = AssistantOrchestrator()

    def post(self, request):
        serializer = RefineTaskArtifactRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_request_user(request)
        task = Task.objects.filter(owner=user, id=serializer.validated_data["task_id"]).first()
        if not task:
            return Response({"detail": "Task not found."}, status=404)

        result = self.orchestrator.refine_task_artifact(
            user=user,
            task=task,
            instruction=serializer.validated_data["instruction"],
            user_timezone=serializer.validated_data.get("timezone") or getattr(request, "cue_timezone", None),
        )

        return Response(
            {
                "reply": result["reply"],
                "task": TaskSerializer(result["task"]).data,
            }
        )
