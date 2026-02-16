from django.utils import timezone

from apps.calendar_sync.models import CalendarEvent
from apps.feed.models import DailyBriefing
from apps.tasks.services import prioritized_tasks_for_user


def build_today_briefing(user):
    today = timezone.localdate()
    top_tasks = prioritized_tasks_for_user(user, limit=3)

    next_event = (
        CalendarEvent.objects.filter(owner=user, starts_at__gte=timezone.now())
        .order_by("starts_at")
        .first()
    )

    summary = {
        "weather": "Sunny, 63F",
        "top_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "due_at": task.due_at.isoformat() if task.due_at else None,
            }
            for task in top_tasks
        ],
        "next_event": (
            {
                "title": next_event.title,
                "starts_at": next_event.starts_at.isoformat(),
                "ends_at": next_event.ends_at.isoformat(),
            }
            if next_event
            else None
        ),
    }

    briefing, _ = DailyBriefing.objects.update_or_create(
        owner=user,
        date=today,
        defaults={"summary": summary},
    )
    return briefing
