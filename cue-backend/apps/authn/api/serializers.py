from rest_framework import serializers


class SocialLoginRequestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "apple"])
    id_token = serializers.CharField(required=False, allow_blank=True)
    access_token = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        provider = attrs.get("provider")
        id_token = (attrs.get("id_token") or "").strip()
        access_token = (attrs.get("access_token") or "").strip()

        if provider == "google":
            if not id_token and not access_token:
                raise serializers.ValidationError("Google login requires id_token or access_token")
        elif provider == "apple":
            if not id_token:
                raise serializers.ValidationError("Apple login requires id_token")

        return attrs


class AuthUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)


class SocialLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = AuthUserSerializer()
