from rest_framework import serializers

from apps.tasks.models import Task
from apps.tasks.services import task_priority_score


class TaskSerializer(serializers.ModelSerializer):
    priority_score = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "notes",
            "metadata_json",
            "metadata_html",
            "due_at",
            "is_hard_deadline",
            "estimated_minutes",
            "urgency",
            "importance",
            "status",
            "follow_up_state",
            "snoozed_until",
            "priority_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "priority_score"]

    def get_priority_score(self, obj: Task) -> int:
        return task_priority_score(obj)
