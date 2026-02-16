from rest_framework import viewsets

from apps.core.services import get_request_user
from apps.tasks.api.serializers import TaskSerializer
from apps.tasks.models import Task, TaskStatus
from apps.tasks.services import log_task_activity


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = get_request_user(self.request)
        queryset = Task.objects.filter(owner=user)

        include_done = self.request.query_params.get("include_done", "false").lower() == "true"
        status = self.request.query_params.get("status")

        if status:
            queryset = queryset.filter(status=status)
        elif not include_done:
            queryset = queryset.exclude(status=TaskStatus.DONE)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        task = serializer.save(owner=get_request_user(self.request))
        log_task_activity(task, action="task_created", actor="user")

    def perform_update(self, serializer):
        task = serializer.save()
        log_task_activity(task, action="task_updated", actor="user")
