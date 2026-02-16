from rest_framework import serializers

from apps.core.models import CrashReport


class CrashReportIngestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrashReport
        fields = [
            "level",
            "error_name",
            "message",
            "stack",
            "source",
            "is_fatal",
            "platform",
            "os_version",
            "app_version",
            "app_build",
            "app_environment",
            "session_id",
            "payload",
            "occurred_at",
        ]

    def validate_payload(self, value):
        return value if isinstance(value, dict) else {}
