from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import get_request_user
from apps.feed.api.serializers import DailyBriefingSerializer
from apps.feed.services import build_today_briefing


class TodayFeedView(APIView):
    def get(self, request):
        user = get_request_user(request)
        briefing = build_today_briefing(user)
        serializer = DailyBriefingSerializer(briefing)
        return Response(serializer.data)
