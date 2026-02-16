from rest_framework import serializers

from apps.feed.models import DailyBriefing


class DailyBriefingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyBriefing
        fields = ["date", "summary", "updated_at"]
