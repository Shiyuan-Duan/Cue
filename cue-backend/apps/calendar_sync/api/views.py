from datetime import timedelta
from datetime import datetime

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calendar_sync.api.serializers import CalendarEventSerializer
from apps.calendar_sync.services import events_between
from apps.core.services import get_request_user


class CalendarEventsView(APIView):
    @staticmethod
    def _parse_dt(value: str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def get(self, request):
        user = get_request_user(request)
        now = timezone.now()
        start = request.query_params.get("from")
        end = request.query_params.get("to")

        if start and end:
            start_dt = self._parse_dt(start)
            end_dt = self._parse_dt(end)
        else:
            start_dt = now
            end_dt = now + timedelta(days=7)

        serializer = CalendarEventSerializer(events_between(user, start_dt, end_dt), many=True)
        return Response(serializer.data)
