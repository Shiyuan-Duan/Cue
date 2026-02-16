from django.urls import path

from .views import TodayFeedView

urlpatterns = [
    path("today", TodayFeedView.as_view(), name="feed-today"),
]
