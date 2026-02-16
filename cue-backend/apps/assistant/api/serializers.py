from rest_framework import serializers


class AssistantMessageRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    session_id = serializers.IntegerField(required=False)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)


class AssistantVoiceTurnRequestSerializer(serializers.Serializer):
    audio = serializers.FileField()
    session_id = serializers.IntegerField(required=False)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)


class ActionCardSerializer(serializers.Serializer):
    type = serializers.CharField()
    task_id = serializers.IntegerField()
    title = serializers.CharField()
    actions = serializers.ListField(child=serializers.CharField())


class AssistantMessageResponseSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    reply = serializers.CharField()
    action_cards = serializers.ListField(child=serializers.DictField(), default=list)


class RefineTaskArtifactRequestSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    instruction = serializers.CharField()
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)
