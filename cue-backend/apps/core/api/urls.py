from django.urls import path

from apps.core.api.views import CrashReportIngestView

urlpatterns = [
    path("crash-reports", CrashReportIngestView.as_view(), name="crash-report-ingest"),
]
