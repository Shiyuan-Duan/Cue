# Core app intentionally keeps shared helpers and no models for now.
from django.conf import settings
from django.db import models


class CrashReport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crash_reports",
    )
    level = models.CharField(max_length=24, default="fatal")
    error_name = models.CharField(max_length=120, blank=True)
    message = models.TextField(blank=True)
    stack = models.TextField(blank=True)
    source = models.CharField(max_length=32, default="js")
    is_fatal = models.BooleanField(default=True)
    platform = models.CharField(max_length=32, blank=True)
    os_version = models.CharField(max_length=64, blank=True)
    app_version = models.CharField(max_length=64, blank=True)
    app_build = models.CharField(max_length=64, blank=True)
    app_environment = models.CharField(max_length=64, blank=True)
    session_id = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["received_at"]),
            models.Index(fields=["platform"]),
            models.Index(fields=["source"]),
            models.Index(fields=["is_fatal"]),
        ]

    def __str__(self):
        return f"{self.platform}:{self.error_name or 'Error'}"
