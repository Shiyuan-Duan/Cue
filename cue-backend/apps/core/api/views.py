import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.serializers import CrashReportIngestSerializer

logger = logging.getLogger("cue.api")


class CrashReportIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CrashReportIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        report = serializer.save(
            user=user,
            ip_address=ip_address or None,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:2000],
        )

        logger.error(
            "CRASH_REPORT_INGESTED id=%s level=%s source=%s fatal=%s platform=%s message=%s",
            report.id,
            report.level,
            report.source,
            report.is_fatal,
            report.platform,
            (report.message or "")[:200],
        )
        return Response({"id": report.id}, status=status.HTTP_201_CREATED)
