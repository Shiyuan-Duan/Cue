import logging
from zoneinfo import ZoneInfo

from django.utils import timezone


logger = logging.getLogger("cue.api")


class RequestTimezoneMiddleware:
    """Activate timezone from request header for per-request datetime handling."""

    HEADER_NAME = "HTTP_X_CUE_TIMEZONE"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = (request.META.get(self.HEADER_NAME) or "").strip()

        if tz_name:
            try:
                tz = ZoneInfo(tz_name)
                timezone.activate(tz)
                request.cue_timezone = tz_name
            except Exception:
                logger.warning("INVALID_TIMEZONE_HEADER value=%s", tz_name)
                timezone.deactivate()
                request.cue_timezone = None
        else:
            timezone.deactivate()
            request.cue_timezone = None

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
