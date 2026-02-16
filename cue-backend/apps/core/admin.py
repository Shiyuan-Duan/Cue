from django.contrib import admin

from apps.core.models import CrashReport


@admin.register(CrashReport)
class CrashReportAdmin(admin.ModelAdmin):
    list_display = ("id", "received_at", "platform", "source", "is_fatal", "error_name")
    list_filter = ("platform", "source", "is_fatal", "level")
    search_fields = ("message", "stack", "error_name", "session_id")
    readonly_fields = (
        "received_at",
        "occurred_at",
        "user",
        "ip_address",
        "user_agent",
        "payload",
    )
