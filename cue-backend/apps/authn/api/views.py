from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authn.api.serializers import SocialLoginRequestSerializer
from apps.authn.services import get_or_create_user_for_identity, verify_social_identity


class SocialLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SocialLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identity = verify_social_identity(
            provider=serializer.validated_data["provider"],
            id_token=serializer.validated_data.get("id_token", ""),
            access_token=serializer.validated_data.get("access_token", ""),
            full_name=serializer.validated_data.get("full_name"),
        )
        user, _ = get_or_create_user_for_identity(identity)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                },
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
            }
        )
