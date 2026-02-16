from datetime import datetime

from .models import UserPreference


def get_or_create_preferences(user):
    preferences, _ = UserPreference.objects.get_or_create(user=user)
    return preferences


def is_within_quiet_hours(preferences: UserPreference, at: datetime) -> bool:
    if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
        return False

    now_time = at.timetz().replace(tzinfo=None)
    start = preferences.quiet_hours_start
    end = preferences.quiet_hours_end

    if start <= end:
        return start <= now_time <= end

    return now_time >= start or now_time <= end
