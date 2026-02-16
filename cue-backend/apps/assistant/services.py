from dataclasses import dataclass
from datetime import timedelta
import logging
import re
import time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.assistant.llm import OpenAILanguageService
from apps.assistant.models import AssistantDecisionLog, ConversationMessage, ConversationSession, Nudge
from apps.preferences.services import get_or_create_preferences, is_within_quiet_hours
from apps.tasks.models import Task
from apps.tasks.services import log_task_activity, prioritized_tasks_for_user, task_priority_score


TASK_INTENT_PATTERN = re.compile(r"(don't forget to|remember to|need to|todo:?)\\s+(.+)", re.IGNORECASE)
logger = logging.getLogger(__name__)


@dataclass
class AssistantResponse:
    session_id: int
    text: str
    action_cards: list[dict]


class NudgeEngine:
    def evaluate(self, user, now=None):
        now = now or timezone.now()
        preferences = get_or_create_preferences(user)

        if is_within_quiet_hours(preferences, now):
            return []

        candidates = []
        for task in prioritized_tasks_for_user(user, limit=5):
            if task.snoozed_until and task.snoozed_until > now:
                continue

            score = task_priority_score(task)
            if score < 8:
                continue

            candidates.append(
                {
                    "task": task,
                    "priority_score": score,
                    "intent": "ask_status",
                    "message": f"Quick check: were you able to finish '{task.title}'?",
                    "reason_codes": ["priority_over_threshold", "assistant_follow_up"],
                }
            )

        return candidates[: preferences.max_nudges_per_day]


class AssistantOrchestrator:
    def __init__(self):
        self.nudge_engine = NudgeEngine()
        self.language_service = OpenAILanguageService()

    def process_message(
        self,
        user,
        text: str,
        session: ConversationSession | None = None,
        user_timezone: str | None = None,
    ) -> AssistantResponse:
        session = session or ConversationSession.objects.create(owner=user, title="Cue Assistant")
        timezone_name = self._resolve_user_timezone(user, user_timezone)
        logger.info(
            "ASSISTANT_TURN_START user_id=%s session_id=%s timezone=%s text=%s",
            user.id,
            session.id,
            timezone_name,
            text[:500],
        )

        ConversationMessage.objects.create(session=session, role="user", content=text)

        if self.language_service.enabled:
            llm_response = self._process_with_llm_agent(
                user=user,
                text=text,
                session=session,
                timezone_name=timezone_name,
            )
            if llm_response:
                logger.info(
                    "ASSISTANT_TURN_END user_id=%s session_id=%s path=llm reply=%s",
                    user.id,
                    session.id,
                    llm_response.text[:500],
                )
                return llm_response

        response = self._process_with_rules(user=user, text=text, session=session)
        logger.info(
            "ASSISTANT_TURN_END user_id=%s session_id=%s path=rules reply=%s",
            user.id,
            session.id,
            response.text[:500],
        )
        return response

    def process_voice_turn(
        self,
        user,
        audio_file,
        session: ConversationSession | None = None,
        user_timezone: str | None = None,
    ) -> dict:
        timezone_name = self._resolve_user_timezone(user, user_timezone)
        started = time.monotonic()
        transcript = self.language_service.transcribe_audio(
            audio_file=audio_file,
            filename=getattr(audio_file, "name", "voice.m4a"),
        )
        transcribe_ms = int((time.monotonic() - started) * 1000)
        if not transcript:
            safe_session = session or ConversationSession.objects.create(owner=user, title="Cue Assistant")
            logger.warning(
                "ASSISTANT_VOICE_TRANSCRIBE_FAILED user_id=%s session_id=%s",
                user.id,
                safe_session.id,
            )
            return {
                "transcript": "",
                "response": AssistantResponse(
                    session_id=safe_session.id,
                    text="I could not hear that clearly. Please try again.",
                    action_cards=[],
                ),
            }

        orchestrate_started = time.monotonic()
        response = self.process_message(
            user=user,
            text=transcript,
            session=session,
            user_timezone=timezone_name,
        )
        orchestrate_ms = int((time.monotonic() - orchestrate_started) * 1000)
        tts_started = time.monotonic()
        speech = self.language_service.synthesize_speech(response.text)
        tts_ms = int((time.monotonic() - tts_started) * 1000)
        total_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "ASSISTANT_VOICE_TURN_TIMING user_id=%s session_id=%s transcribe_ms=%s orchestrate_ms=%s tts_ms=%s total_ms=%s",
            user.id,
            response.session_id,
            transcribe_ms,
            orchestrate_ms,
            tts_ms,
            total_ms,
        )
        return {
            "transcript": transcript,
            "response": response,
            "speech": speech,
        }

    def refine_task_artifact(self, user, task: Task, instruction: str, user_timezone: str | None = None) -> dict:
        timezone_name = self._resolve_user_timezone(user, user_timezone)

        task_payload = {
            "id": task.id,
            "title": task.title,
            "notes": task.notes,
            "status": task.status,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "metadata_json": task.metadata_json or {},
            "metadata_html": task.metadata_html or "",
        }

        llm_result = self.language_service.refine_task_artifact(
            task_payload=task_payload,
            instruction=instruction,
            timezone_name=timezone_name,
        )

        if not llm_result:
            return {
                "reply": "I could not update that task artifact right now.",
                "task": task,
            }

        patch = llm_result.get("task_patch", {})
        if isinstance(patch.get("notes"), str):
            task.notes = patch["notes"][:3000]
        if isinstance(patch.get("metadata_json"), dict):
            task.metadata_json = self._deep_merge(task.metadata_json or {}, patch["metadata_json"])
        if isinstance(patch.get("metadata_html"), str):
            task.metadata_html = patch["metadata_html"][:20000]
        if isinstance(patch.get("due_at_iso"), str):
            parsed = parse_datetime(patch["due_at_iso"])
            if parsed:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                task.due_at = parsed

        task.save(
            update_fields=[
                "notes",
                "metadata_json",
                "metadata_html",
                "due_at",
                "updated_at",
            ]
        )
        log_task_activity(task, action="task_artifact_refined_from_llm_agent", metadata={"instruction": instruction})
        self._refresh_task_render_spec(task, timezone_name)

        return {
            "reply": llm_result.get("reply") or "Task updated.",
            "task": task,
        }

    def _process_with_llm_agent(
        self,
        user,
        text: str,
        session: ConversationSession,
        timezone_name: str,
    ) -> AssistantResponse | None:
        recent_messages = (
            ConversationMessage.objects.filter(session=session)
            .order_by("-created_at")
            .values("role", "content")[:10]
        )
        recent_messages = list(reversed(list(recent_messages)))

        task_context = [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "priority_score": task_priority_score(task),
                "metadata_json": self._compact_metadata_for_llm(task.metadata_json),
            }
            for task in prioritized_tasks_for_user(user, limit=10)
        ]

        plan = self.language_service.plan_turn(
            user_text=text,
            recent_messages=recent_messages,
            tasks=task_context,
            timezone_name=timezone_name,
        )
        if not plan:
            logger.info("ASSISTANT_LLM_PLAN_EMPTY user_id=%s session_id=%s", user.id, session.id)
            return None
        logger.info(
            "ASSISTANT_LLM_PLAN user_id=%s session_id=%s actions=%s reply=%s",
            user.id,
            session.id,
            plan.get("actions", []),
            (plan.get("reply") or "")[:500],
        )

        cards = self._execute_agent_actions(
            user=user,
            actions=plan.get("actions", []),
            timezone_name=timezone_name,
        )
        message = plan.get("reply") or "I updated your plan."

        ConversationMessage.objects.create(
            session=session,
            role="assistant",
            content=message,
            payload={"action_cards": cards},
        )
        self._log_decision(
            user,
            intent="llm_agent_turn",
            score=len(cards) * 5,
            reasons=["openai_planner", f"actions:{len(cards)}"],
        )
        return AssistantResponse(session_id=session.id, text=message, action_cards=cards)

    def _process_with_rules(self, user, text: str, session: ConversationSession) -> AssistantResponse:
        extracted_task = self._extract_task_title(text) or self.language_service.extract_task_title(text)
        if extracted_task:
            due_at = timezone.now() + timedelta(days=2)
            task = Task.objects.create(
                owner=user,
                title=extracted_task,
                due_at=due_at,
                urgency=4,
                importance=4,
            )
            log_task_activity(task, action="task_created_from_assistant")

            message = (
                f"I added '{task.title}' with a suggested due date of "
                f"{task.due_at.strftime('%b %d, %I:%M %p')}. Want me to nudge you today?"
            )
            cards = [
                {
                    "type": "task_created",
                    "task_id": task.id,
                    "title": task.title,
                    "due_at": task.due_at.isoformat(),
                    "actions": ["mark_done", "snooze", "change_due_date", "break_into_steps"],
                }
            ]
            self._log_decision(user, "create_task", task_priority_score(task), ["intent_detected"]) 
        else:
            candidates = self.nudge_engine.evaluate(user)
            if candidates:
                top = candidates[0]
                task = top["task"]
                Nudge.objects.create(
                    owner=user,
                    task=task,
                    kind=top["intent"],
                    message=top["message"],
                    scheduled_at=timezone.now(),
                )
                message = top["message"]
                cards = [
                    {
                        "type": "task_follow_up",
                        "task_id": task.id,
                        "title": task.title,
                        "actions": ["mark_done", "snooze", "set_blocked"],
                    }
                ]
                self._log_decision(user, "task_follow_up", top["priority_score"], top["reason_codes"])
            else:
                message = "You are in good shape. No urgent nudges right now."
                cards = []
                self._log_decision(user, "no_action", 0, ["no_high_priority_tasks"])
            message = self.language_service.rewrite_assistant_reply(message, text)

        ConversationMessage.objects.create(
            session=session,
            role="assistant",
            content=message,
            payload={"action_cards": cards},
        )

        return AssistantResponse(session_id=session.id, text=message, action_cards=cards)

    def _execute_agent_actions(self, user, actions: list[dict], timezone_name: str) -> list[dict]:
        cards: list[dict] = []
        logger.info("ASSISTANT_EXECUTE_ACTIONS user_id=%s actions=%s", user.id, actions)

        for action in actions[:5]:
            if not isinstance(action, dict):
                continue
            action_type = action.get("type")

            if action_type == "create_task":
                title = (action.get("title") or "").strip()
                if not title:
                    continue
                due_at = self._resolve_due_at(action, default_days=2)
                task = Task.objects.create(
                    owner=user,
                    title=title[:200],
                    notes=(action.get("notes") or "")[:1000],
                    metadata_json=action.get("metadata_json") if isinstance(action.get("metadata_json"), dict) else {},
                    metadata_html=(action.get("metadata_html") or "")[:20000],
                    due_at=due_at,
                    estimated_minutes=max(self._safe_int(action.get("estimated_minutes"), 30), 5),
                    urgency=min(max(self._safe_int(action.get("urgency"), 3), 1), 5),
                    importance=min(max(self._safe_int(action.get("importance"), 3), 1), 5),
                )
                log_task_activity(task, action="task_created_from_llm_agent")
                self._refresh_task_render_spec(task, timezone_name)
                logger.info(
                    "ASSISTANT_ACTION_APPLIED type=create_task task_id=%s title=%s due_at=%s",
                    task.id,
                    task.title,
                    task.due_at.isoformat() if task.due_at else None,
                )
                cards.append(
                    {
                        "type": "task_created",
                        "task_id": task.id,
                        "title": task.title,
                        "due_at": task.due_at.isoformat() if task.due_at else None,
                        "actions": ["mark_done", "snooze", "change_due_date", "break_into_steps"],
                    }
                )
                continue

            task = self._resolve_task(user, action)
            if not task:
                continue

            if action_type == "complete_task":
                task.status = "done"
                task.save(update_fields=["status", "updated_at"])
                log_task_activity(task, action="task_completed_from_llm_agent")
                self._refresh_task_render_spec(task, timezone_name, use_llm=False)
                logger.info("ASSISTANT_ACTION_APPLIED type=complete_task task_id=%s", task.id)
                cards.append(
                    {
                        "type": "task_completed",
                        "task_id": task.id,
                        "title": task.title,
                        "actions": ["undo"],
                    }
                )
            elif action_type == "snooze_task":
                hours = max(self._safe_int(action.get("hours"), 24), 1)
                task.status = "snoozed"
                task.snoozed_until = timezone.now() + timedelta(hours=hours)
                task.save(update_fields=["status", "snoozed_until", "updated_at"])
                log_task_activity(task, action="task_snoozed_from_llm_agent", metadata={"hours": hours})
                self._refresh_task_render_spec(task, timezone_name, use_llm=False)
                logger.info("ASSISTANT_ACTION_APPLIED type=snooze_task task_id=%s hours=%s", task.id, hours)
                cards.append(
                    {
                        "type": "task_snoozed",
                        "task_id": task.id,
                        "title": task.title,
                        "actions": ["mark_done", "change_due_date"],
                    }
                )
            elif action_type == "update_task_due":
                task.due_at = self._resolve_due_at(action, default_days=1)
                task.status = "active"
                task.save(update_fields=["due_at", "status", "updated_at"])
                log_task_activity(
                    task,
                    action="task_due_updated_from_llm_agent",
                    metadata={"due_at": task.due_at.isoformat() if task.due_at else None},
                )
                self._refresh_task_render_spec(task, timezone_name, use_llm=False)
                logger.info(
                    "ASSISTANT_ACTION_APPLIED type=update_task_due task_id=%s due_at=%s",
                    task.id,
                    task.due_at.isoformat() if task.due_at else None,
                )
                cards.append(
                    {
                        "type": "task_due_updated",
                        "task_id": task.id,
                        "title": task.title,
                        "due_at": task.due_at.isoformat() if task.due_at else None,
                        "actions": ["mark_done", "snooze"],
                    }
                )
            elif action_type == "update_task_metadata":
                incoming_json = action.get("metadata_json")
                incoming_html = action.get("metadata_html")
                has_render_spec_in_patch = (
                    isinstance(incoming_json, dict) and isinstance(incoming_json.get("render_spec"), dict)
                )
                incoming_title = ""
                if isinstance(incoming_json, dict):
                    raw_title = incoming_json.get("title") or incoming_json.get("render_title")
                    if isinstance(raw_title, str):
                        incoming_title = raw_title.strip()

                if isinstance(incoming_json, dict):
                    task.metadata_json = self._deep_merge(task.metadata_json or {}, incoming_json)
                    # Keep metadata clean when compact summary keys leak back from planner output.
                    task.metadata_json.pop("render_title", None)
                    task.metadata_json.pop("render_block_count", None)
                    if incoming_title:
                        task.title = incoming_title[:200]
                        render_spec = task.metadata_json.get("render_spec")
                        if isinstance(render_spec, dict):
                            render_spec["title"] = task.title
                if isinstance(incoming_html, str):
                    task.metadata_html = incoming_html[:20000]

                update_fields = ["metadata_json", "metadata_html", "updated_at"]
                if incoming_title:
                    update_fields.append("title")
                task.save(update_fields=update_fields)
                log_task_activity(
                    task,
                    action="task_metadata_updated_from_llm_agent",
                    metadata={"keys": list((incoming_json or {}).keys()) if isinstance(incoming_json, dict) else []},
                )
                # If planner already produced render_spec in metadata patch, avoid a second expensive LLM call.
                self._refresh_task_render_spec(
                    task,
                    timezone_name,
                    use_llm=not has_render_spec_in_patch,
                )
                logger.info("ASSISTANT_ACTION_APPLIED type=update_task_metadata task_id=%s", task.id)
                cards.append(
                    {
                        "type": "task_metadata_updated",
                        "task_id": task.id,
                        "title": task.title,
                        "actions": ["open_details"],
                    }
                )

        return cards

    def _resolve_task(self, user, action: dict) -> Task | None:
        task_id = action.get("task_id")
        if task_id:
            return Task.objects.filter(owner=user, id=task_id).first()

        title_contains = (action.get("title_contains") or "").strip()
        if not title_contains:
            return None

        return (
            Task.objects.filter(owner=user, title__icontains=title_contains)
            .order_by("-updated_at")
            .first()
        )

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _resolve_due_at(self, action: dict, default_days: int):
        due_at_iso = (action.get("due_at_iso") or "").strip()
        if due_at_iso:
            parsed = parse_datetime(due_at_iso)
            if parsed is not None:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                return parsed
            logger.warning("ASSISTANT_INVALID_DUE_AT_ISO value=%s", due_at_iso)

        due_in_days = self._safe_int(action.get("due_in_days"), default_days)
        return timezone.now() + timedelta(days=max(due_in_days, 0))

    def _resolve_user_timezone(self, user, user_timezone: str | None) -> str:
        preferences = get_or_create_preferences(user)
        if user_timezone and self._is_valid_timezone(user_timezone) and preferences.timezone != user_timezone:
            preferences.timezone = user_timezone
            preferences.save(update_fields=["timezone", "updated_at"])
        return preferences.timezone or settings.TIME_ZONE

    def _refresh_task_render_spec(self, task: Task, timezone_name: str, use_llm: bool = True):
        task_payload = {
            "id": task.id,
            "title": task.title,
            "notes": task.notes,
            "status": task.status,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "metadata_json": task.metadata_json or {},
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }

        render_spec = None
        if use_llm:
            render_spec = self.language_service.build_task_render_spec(task_payload, timezone_name=timezone_name)
        if not render_spec:
            render_spec = self._fallback_render_spec(task)

        metadata_json = task.metadata_json or {}
        metadata_json["render_spec"] = render_spec
        task.metadata_json = metadata_json
        task.save(update_fields=["metadata_json", "updated_at"])

    @staticmethod
    def _fallback_render_spec(task: Task) -> dict:
        blocks = []
        if task.notes:
            blocks.append({"type": "text", "label": "Notes", "content": task.notes})
        if task.due_at:
            blocks.append({"type": "key_value", "key": "Due", "value": task.due_at.isoformat()})
        blocks.append({"type": "key_value", "key": "Status", "value": task.status})
        return {
            "title": task.title,
            "blocks": blocks,
        }

    def _deep_merge(self, base: dict, patch: dict) -> dict:
        if not isinstance(base, dict):
            base = {}
        if not isinstance(patch, dict):
            return dict(base)
        merged = dict(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _compact_metadata_for_llm(metadata_json: dict | None) -> dict:
        if not isinstance(metadata_json, dict):
            return {}

        compact: dict = {}
        kind = metadata_json.get("kind")
        if isinstance(kind, str):
            compact["kind"] = kind

        shopping_list = metadata_json.get("shopping_list")
        if isinstance(shopping_list, dict):
            items = shopping_list.get("items")
            if isinstance(items, list):
                compact["shopping_list_item_count"] = len(items)

        render_spec = metadata_json.get("render_spec")
        if isinstance(render_spec, dict):
            title = render_spec.get("title")
            blocks = render_spec.get("blocks")
            if isinstance(title, str):
                compact["render_title"] = title[:120]
            if isinstance(blocks, list):
                compact["render_block_count"] = len(blocks)

        return compact

    @staticmethod
    def _is_valid_timezone(tz_name: str) -> bool:
        try:
            ZoneInfo(tz_name)
            return True
        except Exception:
            return False

    def _extract_task_title(self, text: str) -> str | None:
        match = TASK_INTENT_PATTERN.search(text.strip())
        if not match:
            return None
        return match.group(2).strip(" .")

    def _log_decision(self, user, intent: str, score: int, reasons: list[str]):
        AssistantDecisionLog.objects.create(
            owner=user,
            intent=intent,
            priority_score=score,
            reason_codes=reasons,
        )
