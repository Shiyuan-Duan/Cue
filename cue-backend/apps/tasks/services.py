from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from .models import Task, TaskActivityLog, TaskStatus


def log_task_activity(task: Task, action: str, actor: str = "assistant", metadata=None) -> TaskActivityLog:
    return TaskActivityLog.objects.create(
        task=task,
        action=action,
        actor=actor,
        metadata=metadata or {},
    )


def active_tasks_for_user(user) -> QuerySet[Task]:
    return Task.objects.filter(owner=user, status=TaskStatus.ACTIVE)


def task_priority_score(task: Task) -> int:
    score = (task.importance * 3) + (task.urgency * 2)
    now = timezone.now()

    if task.due_at:
        if task.due_at < now:
            score += 12
        elif task.due_at <= now + timedelta(hours=24):
            score += 8
        elif task.due_at <= now + timedelta(days=3):
            score += 4

    if task.last_nudged_at and task.last_nudged_at >= now - timedelta(hours=2):
        score -= 4

    return max(score, 0)


def prioritized_tasks_for_user(user, limit: int = 5):
    tasks = list(active_tasks_for_user(user))
    ranked = sorted(tasks, key=task_priority_score, reverse=True)
    return ranked[:limit]
