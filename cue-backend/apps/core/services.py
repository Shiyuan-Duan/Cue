from django.contrib.auth import get_user_model


User = get_user_model()


DEMO_USERNAME = "cue-demo"


def get_request_user(request):
    if hasattr(request, "user") and request.user and request.user.is_authenticated:
        return request.user
    user, _ = User.objects.get_or_create(
        username=DEMO_USERNAME,
        defaults={"email": "demo@cue.local"},
    )
    return user
