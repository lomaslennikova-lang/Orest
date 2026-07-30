"""Validation and private filesystem storage for supported receipt files."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_actions.runtime import AIRuntimeSettings
from app.models import AIReceiptAttachment


MAX_RECEIPT_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_SIDE_PX = 4_000
SUPPORTED_MEDIA_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
_SAFE_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}\.(pdf|png|jpg)$")


class ReceiptValidationError(ValueError):
    """Raised when an attachment is not an allowed, bounded receipt file."""


@dataclass(frozen=True)
class ValidatedReceipt:
    media_type: str
    byte_size: int
    content_sha256: str


@dataclass(frozen=True)
class StoredReceipt:
    original_filename: str
    media_type: str
    byte_size: int
    content_sha256: str
    storage_key: str
    stored_at: datetime


def _normalise_filename(filename: str) -> str:
    normalised = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not normalised or len(normalised) > 255 or "\x00" in normalised:
        raise ReceiptValidationError("Назва файла чеку некоректна.")
    return normalised


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while index < len(data):
        if data[index] != 0xFF:
            raise ReceiptValidationError("JPEG-файл має некоректну структуру.")
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in sof_markers:
            if segment_length < 7:
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    raise ReceiptValidationError("Не вдалося визначити роздільність JPEG-файла.")


def _validate_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ReceiptValidationError("Зображення має некоректну роздільність.")
    if width > MAX_IMAGE_SIDE_PX or height > MAX_IMAGE_SIDE_PX:
        raise ReceiptValidationError("Розмір сторони зображення перевищує 4000 px.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ReceiptValidationError("Роздільність зображення перевищує 12 мегапікселів.")


def _validate_png(data: bytes) -> None:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ReceiptValidationError("PNG-файл має некоректну структуру.")
    _validate_dimensions(
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def _validate_pdf(data: bytes) -> None:
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ReceiptValidationError("Зашифровані PDF-чеки не підтримуються.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ReceiptValidationError("PDF-чек не може містити більше 5 сторінок.")
    except ReceiptValidationError:
        raise
    except (PdfReadError, ValueError, OSError) as error:
        raise ReceiptValidationError("PDF-файл пошкоджений або не підтримується.") from error


def validate_receipt_content(content: bytes, filename: str) -> ValidatedReceipt:
    """Validate real content signatures and structural bounds, not client MIME data."""

    _normalise_filename(filename)
    if not content:
        raise ReceiptValidationError("Файл чеку порожній.")
    if len(content) > MAX_RECEIPT_BYTES:
        raise ReceiptValidationError("Розмір файла чеку не може перевищувати 5 МіБ.")

    if content.startswith(b"%PDF-"):
        media_type = "application/pdf"
        _validate_pdf(content)
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
        _validate_png(content)
    elif content.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
        _validate_dimensions(*_jpeg_dimensions(content))
    else:
        raise ReceiptValidationError("Дозволені лише PDF, PNG або JPEG чеки.")

    return ValidatedReceipt(
        media_type=media_type,
        byte_size=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
    )


class ReceiptStorage:
    """Stores server-validated receipt bytes under generated, non-public names."""

    def __init__(self, settings: AIRuntimeSettings):
        self._root = settings.receipt_storage_dir.resolve()

    def _path_for_key(self, storage_key: str) -> Path:
        if not _SAFE_STORAGE_KEY.fullmatch(storage_key):
            raise ReceiptValidationError("Некоректний ключ зберігання чеку.")
        path = (self._root / storage_key).resolve()
        if path.parent != self._root:
            raise ReceiptValidationError("Некоректний шлях зберігання чеку.")
        return path

    def store(self, content: bytes, filename: str) -> StoredReceipt:
        """Validate then atomically persist a receipt without trusting its name or MIME."""

        original_filename = _normalise_filename(filename)
        validated = validate_receipt_content(content, original_filename)
        self._root.mkdir(parents=True, exist_ok=True)
        storage_key = f"{uuid4().hex}{SUPPORTED_MEDIA_TYPES[validated.media_type]}"
        target = self._path_for_key(storage_key)
        descriptor, temporary_path = tempfile.mkstemp(prefix=".upload-", dir=self._root)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, target)
            try:
                target.chmod(0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

        return StoredReceipt(
            original_filename=original_filename,
            media_type=validated.media_type,
            byte_size=validated.byte_size,
            content_sha256=validated.content_sha256,
            storage_key=storage_key,
            stored_at=datetime.now(timezone.utc),
        )

    def delete(self, storage_key: str) -> None:
        """Delete a generated receipt file; missing files are already cleaned up."""

        try:
            self._path_for_key(storage_key).unlink(missing_ok=True)
        except OSError as error:
            raise RuntimeError("Не вдалося видалити прострочений файл чеку.") from error


async def cleanup_expired_receipts(
    session: AsyncSession,
    storage: ReceiptStorage,
    *,
    now: datetime | None = None,
) -> int:
    """Remove expired receipt files and metadata; the caller owns the DB commit."""

    current_time = now or datetime.now(timezone.utc)
    result = await session.execute(
        select(AIReceiptAttachment).where(AIReceiptAttachment.expires_at <= current_time),
    )
    attachments = result.scalars().all()
    for attachment in attachments:
        storage.delete(attachment.storage_key)
        await session.delete(attachment)
    return len(attachments)
