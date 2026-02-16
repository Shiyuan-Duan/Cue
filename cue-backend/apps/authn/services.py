import base64
import json
import logging
from urllib.request import Request, urlopen
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
except Exception:  # pragma: no cover
    google_id_token = None
    google_requests = None


logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class SocialIdentity:
    provider: str
    subject: str
    email: str | None
    full_name: str | None


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _decode_jwt_unverified(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise AuthenticationFailed("Invalid token format")
    payload_raw = base64.urlsafe_b64decode(_pad_b64(parts[1])).decode("utf-8")
    return json.loads(payload_raw)


def _verify_google_id_token(id_token: str) -> dict:
    if settings.CUE_SOCIAL_AUTH_RELAXED:
        logger.warning("AUTH_RELAXED_MODE enabled: Google token signature not verified")
        return _decode_jwt_unverified(id_token)

    if google_id_token is None or google_requests is None:
        raise AuthenticationFailed("Google verification library missing")

    request = google_requests.Request()
    audience = settings.GOOGLE_OAUTH_CLIENT_ID or None
    payload = google_id_token.verify_oauth2_token(id_token, request, audience=audience)
    return payload


def _verify_google_access_token(access_token: str) -> dict:
    request = Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urlopen(request, timeout=6) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
    except Exception as exc:
        raise AuthenticationFailed("Invalid Google access token") from exc

    if not payload.get("sub"):
        raise AuthenticationFailed("Google userinfo missing subject")
    return payload


def _verify_apple_id_token(id_token: str) -> dict:
    # In strict mode you'd validate signature using Apple's JWKS.
    # For this MVP we run relaxed mode unless explicitly disabled.
    if not settings.CUE_SOCIAL_AUTH_RELAXED:
        raise AuthenticationFailed("Apple strict verification not configured")
    logger.warning("AUTH_RELAXED_MODE enabled: Apple token signature not verified")
    return _decode_jwt_unverified(id_token)


def verify_social_identity(
    provider: str,
    id_token: str = "",
    access_token: str = "",
    full_name: str | None = None,
) -> SocialIdentity:
    provider = provider.lower().strip()

    if provider == "google":
        if id_token:
            payload = _verify_google_id_token(id_token)
        elif access_token:
            payload = _verify_google_access_token(access_token)
        else:
            raise AuthenticationFailed("Google login requires id_token or access_token")
        subject = str(payload.get("sub") or "")
        email = payload.get("email")
        name = payload.get("name") or full_name
    elif provider == "apple":
        payload = _verify_apple_id_token(id_token)
        subject = str(payload.get("sub") or "")
        email = payload.get("email")
        name = full_name
    else:
        raise AuthenticationFailed("Unsupported provider")

    if not subject:
        raise AuthenticationFailed("Token missing subject")

    return SocialIdentity(provider=provider, subject=subject, email=email, full_name=name)


def get_or_create_user_for_identity(identity: SocialIdentity):
    username = f"{identity.provider}_{identity.subject}"[:150]
    defaults = {
        "email": identity.email or "",
        "first_name": (identity.full_name or "")[:150],
    }
    user, created = User.objects.get_or_create(username=username, defaults=defaults)

    updated = False
    if identity.email and user.email != identity.email:
        user.email = identity.email
        updated = True
    if identity.full_name and not user.first_name:
        user.first_name = identity.full_name[:150]
        updated = True
    if updated:
        user.save(update_fields=["email", "first_name"])

    return user, created
