# Cue Backend (Django)

## What is scaffolded
- Modular domain apps: `tasks`, `assistant`, `feed`, `calendar_sync`, `preferences`
- Service-layer business logic in each app (`services.py`)
- REST endpoints:
  - `POST /api/auth/social-login`
  - `POST /api/auth/refresh`
  - `GET /api/auth/me`
  - `GET/POST/PATCH/DELETE /api/tasks/`
  - `POST /api/assistant/message`
  - `POST /api/core/crash-reports`
  - `GET /api/feed/today`
  - `GET /api/calendar/events`
- Deterministic priority + nudge logic in `apps/tasks/services.py` and `apps/assistant/services.py`

## Setup
```bash
cd cue-backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

## Notes
- This MVP uses a fallback demo user (`cue-demo`) when not authenticated.
- Weather in feed is currently mocked (`Sunny, 63F`).
- Google Calendar sync and Celery workers are not wired yet; models are in place for next phase.
- Configure env in `cue-backend/.env` (see `cue-backend/.env.example`).
- Optional OpenAI chatbot layer uses `OPENAI_API_KEY` and `OPENAI_MODEL`.
- Deterministic logic still handles task creation/prioritization if OpenAI is unavailable.
- Social auth supports Google + Apple token exchange via `/api/auth/social-login`.
- For production, disable relaxed mode by setting `CUE_SOCIAL_AUTH_RELAXED=false` and configure provider verification.
- Verbose API/chat logging can be controlled with:
  - `CUE_VERBOSE_API_LOGGING=true|false`
  - `DJANGO_LOG_LEVEL=INFO|DEBUG|WARNING`

## Debug logs to share
- Request/response logs for API calls are emitted as `API_REQUEST` and `API_RESPONSE`.
- Assistant turn logs are emitted as `ASSISTANT_*` and `OPENAI_*`.
- Client crash reports are emitted as `CRASH_REPORT_INGESTED` and stored in `core_crashreport`.
