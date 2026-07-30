from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfWriter

from app.ai_actions.audit import AuditLogWriter, cleanup_expired_audit_logs
from app.ai_actions.receipts import (
    MAX_RECEIPT_BYTES,
    ReceiptStorage,
    ReceiptValidationError,
    validate_receipt_content,
)
from app.ai_actions.runtime import AIRuntimeSettings, get_ai_runtime_settings


def png_bytes(width: int = 100, height: int = 200) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(
        4,
        "big",
    ) + height.to_bytes(4, "big")


def pdf_bytes(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class AIActionRuntimeTests(unittest.TestCase):
    def test_receipt_validation_uses_content_signature_and_image_bounds(self):
        validated = validate_receipt_content(png_bytes(), "receipt.pdf")

        self.assertEqual(validated.media_type, "image/png")
        with self.assertRaises(ReceiptValidationError):
            validate_receipt_content(png_bytes(width=4001), "receipt.png")
        with self.assertRaises(ReceiptValidationError):
            validate_receipt_content(b"not a receipt", "receipt.pdf")
        with self.assertRaises(ReceiptValidationError):
            validate_receipt_content(b"x" * (MAX_RECEIPT_BYTES + 1), "receipt.pdf")

    def test_pdf_page_limit_is_checked(self):
        self.assertEqual(
            validate_receipt_content(pdf_bytes(5), "receipt.pdf").media_type,
            "application/pdf",
        )
        with self.assertRaises(ReceiptValidationError):
            validate_receipt_content(pdf_bytes(6), "receipt.pdf")

    def test_receipt_storage_uses_generated_private_filename(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = AIRuntimeSettings(root / "receipts", root / "audit", 180, 30)
            stored = ReceiptStorage(settings).store(png_bytes(), "../my receipt.png")

            self.assertEqual(stored.original_filename, "my receipt.png")
            self.assertTrue((settings.receipt_storage_dir / stored.storage_key).is_file())
            self.assertNotIn("receipt", stored.storage_key)

    def test_audit_log_is_jsonl_and_cleanup_keeps_retention_window(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = AIRuntimeSettings(root / "receipts", root / "audit", 180, 30)
            executed_at = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
            AuditLogWriter(settings).append_executed_action(
                action_id=uuid4(),
                conversation_id=uuid4(),
                actor_username="admin",
                payload={"transactions": [{"amount": "10.00"}]},
                created_transaction_ids=[12],
                attachment_sha256="a" * 64,
                executed_at=executed_at,
            )
            log_path = settings.audit_log_dir / "ai-actions-2026-07-30.jsonl"
            record = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "ai_action_executed")
            self.assertEqual(record["created_transaction_ids"], [12])

            old_path = settings.audit_log_dir / "ai-actions-2026-06-29.jsonl"
            old_path.write_text("{}\n", encoding="utf-8")
            self.assertEqual(cleanup_expired_audit_logs(settings, today=date(2026, 7, 30)), 1)
            self.assertFalse(old_path.exists())
            self.assertTrue(log_path.exists())

    def test_runtime_settings_reject_non_positive_retention(self):
        previous = os.environ.get("AI_RECEIPT_RETENTION_DAYS")
        os.environ["AI_RECEIPT_RETENTION_DAYS"] = "0"
        try:
            with self.assertRaisesRegex(RuntimeError, "positive integer"):
                get_ai_runtime_settings()
        finally:
            if previous is None:
                del os.environ["AI_RECEIPT_RETENTION_DAYS"]
            else:
                os.environ["AI_RECEIPT_RETENTION_DAYS"] = previous
