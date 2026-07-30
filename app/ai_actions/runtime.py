"""Configurable, private runtime storage for receipt processing and audit logs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_STORAGE_DIR = Path("runtime/ai-receipts")
DEFAULT_AUDIT_LOG_DIR = Path("runtime/ai-audit")


class AIRuntimeConfigurationError(RuntimeError):
    """Raised when a runtime-storage setting is unsafe or invalid."""


def _configured_path(name: str, default: Path) -> Path:
    configured = os.getenv(name)
    path = Path(configured) if configured else default
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _positive_integer(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise AIRuntimeConfigurationError(f"{name} must be a positive integer.") from error
    if parsed <= 0:
        raise AIRuntimeConfigurationError(f"{name} must be a positive integer.")
    return parsed


@dataclass(frozen=True)
class AIRuntimeSettings:
    receipt_storage_dir: Path
    audit_log_dir: Path
    receipt_retention_days: int
    audit_log_retention_days: int


def get_ai_runtime_settings() -> AIRuntimeSettings:
    """Read non-secret AI runtime settings from the environment."""

    return AIRuntimeSettings(
        receipt_storage_dir=_configured_path(
            "AI_RECEIPT_STORAGE_DIR",
            DEFAULT_RECEIPT_STORAGE_DIR,
        ),
        audit_log_dir=_configured_path("AI_AUDIT_LOG_DIR", DEFAULT_AUDIT_LOG_DIR),
        receipt_retention_days=_positive_integer("AI_RECEIPT_RETENTION_DAYS", 180),
        audit_log_retention_days=_positive_integer("AI_AUDIT_LOG_RETENTION_DAYS", 30),
    )


def ensure_ai_runtime_directories(settings: AIRuntimeSettings) -> None:
    """Create private service directories; callers must not expose them over HTTP."""

    for directory in (settings.receipt_storage_dir, settings.audit_log_dir):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            # Windows and managed volumes may not support POSIX permissions.
            # The directory remains private through the host/container ACL.
            pass
