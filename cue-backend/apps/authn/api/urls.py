from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import MeView, SocialLoginView

urlpatterns = [
    path("social-login", SocialLoginView.as_view(), name="social-login"),
    path("refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("me", MeView.as_view(), name="auth-me"),
]
