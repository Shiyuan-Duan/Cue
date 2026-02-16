import json
import logging
import re
import base64
from datetime import datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from django.conf import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


logger = logging.getLogger(__name__)


class OpenAILanguageService:
    def __init__(self):
        self.model = settings.CUE_OPENAI_MODEL
        self.client = None

        if settings.CUE_OPENAI_API_KEY and OpenAI is not None:
            self.client = OpenAI(api_key=settings.CUE_OPENAI_API_KEY)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def rewrite_assistant_reply(self, draft_reply: str, user_text: str) -> str:
        if not self.enabled:
            return draft_reply

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are Cue, a concise personal assistant. "
                            "Keep the same action intent as the draft, but make language natural and human."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"User message: {user_text}\n"
                            f"Draft assistant reply: {draft_reply}\n"
                            "Return only the improved final reply."
                        ),
                    },
                ],
            )
            rewritten = getattr(response, "output_text", "") or ""
            return rewritten.strip() or draft_reply
        except Exception:
            logger.exception("OpenAI rewrite failed, using deterministic reply")
            return draft_reply

    def extract_task_title(self, text: str) -> str | None:
        if not self.enabled:
            return None

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Extract one actionable to-do title from user text if present. "
                            "Return only the task title, or NONE if no to-do intent."
                        ),
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )
            output = (getattr(response, "output_text", "") or "").strip()
            if not output or output.upper() == "NONE":
                return None
            return output[:200]
        except Exception:
            logger.exception("OpenAI extraction failed")
            return None

    def plan_turn(
        self,
        user_text: str,
        recent_messages: list[dict],
        tasks: list[dict],
        timezone_name: str = "UTC",
    ) -> dict | None:
        if not self.enabled:
            return None

        now_local = datetime.now(ZoneInfo(timezone_name))
        prompt_payload = {
            "timezone": timezone_name,
            "now_local": now_local.isoformat(),
            "now_utc": datetime.now(timezone.utc).isoformat(),
            "user_text": user_text,
            "recent_messages": recent_messages,
            "tasks": tasks,
            "action_schema": [
                {
                    "type": "create_task",
                    "title": "string",
                    "notes": "string_optional",
                    "metadata_json": "object_optional",
                    "metadata_html": "string_optional",
                    "due_at_iso": "ISO8601 datetime string optional",
                    "due_in_days": "number_optional",
                    "estimated_minutes": "number_optional",
                    "urgency": "1-5_optional",
                    "importance": "1-5_optional",
                },
                {
                    "type": "complete_task",
                    "task_id": "number_optional",
                    "title_contains": "string_optional",
                },
                {
                    "type": "snooze_task",
                    "task_id": "number_optional",
                    "title_contains": "string_optional",
                    "hours": "number_optional",
                },
                {
                    "type": "update_task_due",
                    "task_id": "number_optional",
                    "title_contains": "string_optional",
                    "due_at_iso": "ISO8601 datetime string preferred",
                    "due_in_days": "number_optional",
                },
                {
                    "type": "update_task_metadata",
                    "task_id": "number_optional",
                    "title_contains": "string_optional",
                    "metadata_json": "object_optional",
                    "metadata_html": "string_optional",
                },
            ],
            "output_contract": {
                "reply": "string",
                "actions": "array of action objects",
            },
        }

        try:
            logger.info(
                "OPENAI_PLAN_REQUEST model=%s timezone=%s user_text=%s recent_messages=%s task_count=%s",
                self.model,
                timezone_name,
                user_text[:300],
                len(recent_messages),
                len(tasks),
            )
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are Cue, a personal assistant that can drive backend task operations. "
                            "Interpret the user's intent and output STRICT JSON only. "
                            "Be concise and natural in reply text. "
                            "Use the provided timezone and current local time when interpreting dates/times. "
                            "When user gives a concrete date/time (for example 'Feb 19 noon'), prefer due_at_iso "
                            "instead of due_in_days, and due_at_iso must include timezone offset matching the provided timezone. "
                            "Do not invent large due_in_days values for explicit date/time requests. "
                            "For shopping/grocery/buying tasks, include metadata_json with structure like "
                            "{\"kind\":\"shopping_list\",\"shopping_list\":{\"items\":[{\"label\":\"Milk\",\"done\":false}]}}. "
                            "If user asks to add/remove shopping items, use update_task_metadata action. "
                            "If no backend write is needed, return actions as []."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt_payload, ensure_ascii=False),
                    },
                ],
            )
            output = (getattr(response, "output_text", "") or "").strip()
            logger.info("OPENAI_PLAN_RAW_RESPONSE model=%s output=%s", self.model, output[:1000])
            payload = self._extract_json_object(output)
            if not isinstance(payload, dict):
                logger.warning("OPENAI_PLAN_PARSE_FAILED output=%s", output[:1000])
                return None

            reply = payload.get("reply")
            actions = payload.get("actions")
            if not isinstance(reply, str) or not isinstance(actions, list):
                return None
            return {
                "reply": reply.strip(),
                "actions": actions,
            }
        except Exception:
            logger.exception("OpenAI planning failed")
            return None

    def transcribe_audio(self, audio_file, filename: str = "voice.m4a") -> str | None:
        if not self.enabled:
            return None

        try:
            raw = audio_file.read()
            if not raw:
                return None

            stream = BytesIO(raw)
            stream.name = filename
            result = self.client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=stream,
            )
            transcript = (getattr(result, "text", "") or "").strip()
            return transcript or None
        except Exception:
            logger.exception("OpenAI transcription failed")
            return None

    def synthesize_speech(
        self,
        text: str,
        voice: str = "coral",
        instructions: str = "Speak naturally, concise, and friendly.",
        response_format: str = "mp3",
    ) -> dict | None:
        if not self.enabled:
            return None
        text = (text or "").strip()
        if not text:
            return None

        try:
            response = self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                instructions=instructions,
                response_format=response_format,
            )

            raw: bytes | None = None
            if hasattr(response, "read"):
                try:
                    raw = response.read()
                except Exception:
                    raw = None
            if raw is None and hasattr(response, "content"):
                maybe_content = getattr(response, "content", None)
                if isinstance(maybe_content, (bytes, bytearray)):
                    raw = bytes(maybe_content)
            if not raw:
                return None

            mime_type = "audio/mpeg" if response_format == "mp3" else "audio/wav"
            return {
                "audio_base64": base64.b64encode(raw).decode("ascii"),
                "mime_type": mime_type,
                "format": response_format,
            }
        except Exception:
            logger.exception("OpenAI speech synthesis failed")
            return None

    def build_task_render_spec(self, task_payload: dict, timezone_name: str = "UTC") -> dict | None:
        if not self.enabled:
            return None

        prompt_payload = {
            "timezone": timezone_name,
            "task": task_payload,
            "output_contract": {
                "title": "string",
                "blocks": [
                    {
                        "type": "text | key_value | list | checklist",
                        "label": "string_optional",
                        "content": "string_optional",
                        "key": "string_optional",
                        "value": "string_optional",
                        "items": "string[] or [{label:string,done:boolean}]",
                    }
                ],
            },
        }

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You generate UI render specs for task detail pages. "
                            "Return STRICT JSON only with title + blocks. "
                            "Blocks must be compact and practical for mobile rendering. "
                            "Prefer checklist for actionable item collections, list for plain bullets."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt_payload, ensure_ascii=False),
                    },
                ],
            )
            output = (getattr(response, "output_text", "") or "").strip()
            payload = self._extract_json_object(output)
            if not isinstance(payload, dict):
                logger.warning("OPENAI_RENDER_SPEC_PARSE_FAILED output=%s", output[:1000])
                return None

            blocks = payload.get("blocks")
            if not isinstance(blocks, list):
                return None

            title = payload.get("title")
            if not isinstance(title, str):
                title = task_payload.get("title", "Task")

            return {
                "title": title[:200],
                "blocks": blocks[:20],
            }
        except Exception:
            logger.exception("OpenAI render spec generation failed")
            return None

    def refine_task_artifact(
        self,
        task_payload: dict,
        instruction: str,
        timezone_name: str = "UTC",
    ) -> dict | None:
        if not self.enabled:
            return None

        prompt_payload = {
            "timezone": timezone_name,
            "task": task_payload,
            "instruction": instruction,
            "output_contract": {
                "reply": "string",
                "task_patch": {
                    "notes": "string_optional",
                    "metadata_json": "object_optional",
                    "metadata_html": "string_optional",
                    "due_at_iso": "ISO8601_optional",
                },
            },
        }

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You update one existing task artifact based on user instruction. "
                            "Return STRICT JSON only with reply + task_patch. "
                            "Patch only relevant fields and preserve existing structure where possible."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt_payload, ensure_ascii=False),
                    },
                ],
            )
            output = (getattr(response, "output_text", "") or "").strip()
            payload = self._extract_json_object(output)
            if not isinstance(payload, dict):
                logger.warning("OPENAI_REFINE_PARSE_FAILED output=%s", output[:1000])
                return None

            reply = payload.get("reply")
            task_patch = payload.get("task_patch")
            if not isinstance(reply, str) or not isinstance(task_patch, dict):
                return None

            return {
                "reply": reply.strip(),
                "task_patch": task_patch,
            }
        except Exception:
            logger.exception("OpenAI artifact refinement failed")
            return None

    @staticmethod
    def _extract_json_object(raw: str):
        raw = raw.strip()
        if not raw:
            return None

        try:
            return json.loads(raw)
        except Exception:
            pass

        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except Exception:
                return None

        obj_match = re.search(r"(\{.*\})", raw, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except Exception:
                return None

        return None
