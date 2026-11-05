"""Git-Ops CI/CD Automation Webhook Endpoints.

Receives GitHub Actions git push webhooks, arms/disarms autonomous watchdog,
and logs real-time pipeline deployment events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .state import get_git_metadata, state
from .telemetry import get_system_status

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


class GitPushWebhookPayload(BaseModel):
    branch: str = Field(default="main")
    commit: str = Field(default="HEAD")
    author: str = Field(default="Developer")
    message: str = Field(default="git push deployment")
    mode: str = Field(default="auto_watchdog")  # 'auto_watchdog' | 'manual_control'


@router.post("/git-push")
def receive_git_push_event(payload: GitPushWebhookPayload) -> dict[str, Any]:
    git_meta = get_git_metadata()
    event_record = {
        "branch": payload.branch or git_meta["branch"],
        "commit": payload.commit if payload.commit != "HEAD" else git_meta["commit"],
        "author": payload.author if payload.author != "Developer" else git_meta["author"],
        "message": payload.message if payload.message != "git push deployment" else git_meta["message"],
        "mode": payload.mode,
        "received_at": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    }
    with state._lock:
        state.last_git_push_event = event_record
        if payload.mode == "auto_watchdog":
            state.watchdog_enabled = True
        elif payload.mode == "manual_control":
            state.watchdog_enabled = False

    state.add_log(
        source="git-push",
        account="CI/CD",
        message=(
            f"🚀 Git Push detected [{event_record['branch']}@{event_record['commit']}] by {event_record['author']}: "
            f"Deployed Health Probes across AWS & Azure (Mode={payload.mode.upper()})"
        ),
        level="SUCCESS",
    )
    state.run_probe_cycle(include_anycast=True)
    return {"status": "ok", "git_push_event": event_record, "system": get_system_status()}

