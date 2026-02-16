from django.conf import settings
from django.db import models


class TaskStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DONE = "done", "Done"
    SNOOZED = "snoozed", "Snoozed"
    BLOCKED = "blocked", "Blocked"


class FollowUpState(models.TextChoices):
    CREATED = "created", "Created"
    PLAN_SUGGESTED = "plan_suggested", "Plan Suggested"
    CHECKED_IN = "checked_in", "Checked In"
    CLOSED = "closed", "Closed"


class Task(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    metadata_html = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    is_hard_deadline = models.BooleanField(default=False)
    estimated_minutes = models.PositiveIntegerField(default=30)
    urgency = models.PositiveSmallIntegerField(default=3)
    importance = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(max_length=16, choices=TaskStatus.choices, default=TaskStatus.ACTIVE)
    follow_up_state = models.CharField(
        max_length=20,
        choices=FollowUpState.choices,
        default=FollowUpState.CREATED,
    )
    snoozed_until = models.DateTimeField(null=True, blank=True)
    last_nudged_at = models.DateTimeField(null=True, blank=True)
    nudge_count_today = models.PositiveSmallIntegerField(default=0)
    recurrence_rule = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "-urgency", "-importance", "created_at"]

    def __str__(self):
        return self.title


class TaskActivityLog(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activity_logs")
    actor = models.CharField(max_length=24, default="assistant")
    action = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
