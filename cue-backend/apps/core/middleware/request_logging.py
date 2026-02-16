import json
import logging
import time

from django.conf import settings


logger = logging.getLogger("cue.api")


class ApiRequestLoggingMiddleware:
    """Logs request/response details for /api/* endpoints in development."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._should_log(request):
            return self.get_response(request)

        started = time.monotonic()
        body_preview = self._extract_body_preview(request)

        logger.info(
            "API_REQUEST method=%s path=%s query=%s timezone=%s body=%s",
            request.method,
            request.path,
            request.META.get("QUERY_STRING", ""),
            request.META.get("HTTP_X_CUE_TIMEZONE", ""),
            body_preview,
        )

        response = self.get_response(request)

        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "API_RESPONSE method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )

        return response

    @staticmethod
    def _should_log(request) -> bool:
        return bool(getattr(settings, "CUE_VERBOSE_API_LOGGING", False)) and request.path.startswith("/api/")

    @staticmethod
    def _extract_body_preview(request) -> str:
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return ""
        content_type = (request.META.get("CONTENT_TYPE") or "").lower()
        if "multipart/form-data" in content_type:
            length = request.META.get("CONTENT_LENGTH", "")
            return f"<multipart omitted content_type={content_type} content_length={length}>"

        try:
            raw = request.body.decode("utf-8", errors="ignore")
            if not raw:
                return ""
            try:
                parsed = json.loads(raw)
                rendered = json.dumps(parsed, ensure_ascii=True)
            except Exception:
                rendered = raw
            if len(rendered) > 500:
                return f"{rendered[:500]}..."
            return rendered
        except Exception:
            return "<unavailable>"
