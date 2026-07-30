"""Append-only JSONL audit records for successfully confirmed AI actions."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence
from uuid import UUID

from app.ai_actions.runtime import AIRuntimeSettings


_AUDIT_FILENAME = re.compile(r"^ai-actions-(\d{4}-\d{2}-\d{2})\.jsonl$")
_AUDIT_WRITE_LOCK = threading.Lock()


class AuditLogWriter:
    """Writes only successful executed actions as one JSON object per line."""

    def __init__(self, settings: AIRuntimeSettings):
        self._directory = settings.audit_log_dir.resolve()

    def _path_for_day(self, day: date) -> Path:
        return self._directory / f"ai-actions-{day.isoformat()}.jsonl"

    def append_executed_action(
        self,
        *,
        action_id: UUID,
        conversation_id: UUID,
        actor_username: str,
        payload: Mapping[str, object],
        created_transaction_ids: Sequence[int],
        attachment_sha256: str | None,
        executed_at: datetime | None = None,
    ) -> None:
        """Durably append the exact executed payload after a successful confirm."""

        timestamp = executed_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("executed_at must be timezone-aware")
        event = {
            "timestamp_utc": timestamp.astimezone(timezone.utc).isoformat(),
            "event": "ai_action_executed",
            "action_id": str(action_id),
            "conversation_id": str(conversation_id),
            "actor": actor_username,
            "action_type": "create_expense_transactions",
            "payload": payload,
            "created_transaction_ids": list(created_transaction_ids),
            "attachment_sha256": attachment_sha256,
        }
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for_day(timestamp.date())

        with _AUDIT_WRITE_LOCK:
            descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "a", encoding="utf-8") as file:
                    file.write(f"{line}\n")
                    file.flush()
                    os.fsync(file.fileno())
            finally:
                try:
                    path.chmod(0o600)
                except OSError:
                    pass


def cleanup_expired_audit_logs(
    settings: AIRuntimeSettings,
    *,
    today: date | None = None,
) -> int:
    """Delete only rotated daily JSONL files older than configured retention."""

    current_day = today or datetime.now(timezone.utc).date()
    oldest_retained_day = current_day - timedelta(days=settings.audit_log_retention_days)
    deleted = 0
    directory = settings.audit_log_dir.resolve()
    if not directory.exists():
        return deleted

    for path in directory.iterdir():
        match = _AUDIT_FILENAME.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        try:
            file_day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if file_day < oldest_retained_day:
            path.unlink()
            deleted += 1
    return deleted
