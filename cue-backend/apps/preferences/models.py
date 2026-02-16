from django.conf import settings
from django.db import models


class AssistantStyle(models.TextChoices):
    GENTLE = "gentle", "Gentle"
    PROACTIVE = "proactive", "Proactive"
    STRICT = "strict", "Strict"


class UserPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=64, default="UTC")
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    max_nudges_per_day = models.PositiveSmallIntegerField(default=4)
    assistant_style = models.CharField(
        max_length=16,
        choices=AssistantStyle.choices,
        default=AssistantStyle.PROACTIVE,
    )
    briefing_hour = models.PositiveSmallIntegerField(default=8)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences<{self.user_id}>"
