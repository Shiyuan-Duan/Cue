from rest_framework import serializers

from apps.calendar_sync.models import CalendarEvent


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "title",
            "starts_at",
            "ends_at",
            "location",
            "is_all_day",
        ]
