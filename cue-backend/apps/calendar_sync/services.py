from datetime import datetime

from apps.calendar_sync.models import CalendarEvent


def events_between(user, start: datetime, end: datetime):
    return CalendarEvent.objects.filter(owner=user, starts_at__lt=end, ends_at__gt=start)
