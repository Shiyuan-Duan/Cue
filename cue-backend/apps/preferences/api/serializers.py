from rest_framework import serializers

from apps.preferences.models import UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            "timezone",
            "quiet_hours_start",
            "quiet_hours_end",
            "max_nudges_per_day",
            "assistant_style",
            "briefing_hour",
        ]
