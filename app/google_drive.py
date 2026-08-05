"""Small server-side Google Drive OAuth and private-file client.

Secrets are read only from environment variables.  This module deliberately uses
the standard library so the deployment has no SDK-specific credential cache.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"


class GoogleDriveConfigurationError(RuntimeError):
    pass


class GoogleDriveOAuthError(RuntimeError):
    pass


class GoogleDriveOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleDriveSettings:
    client_id: str
    client_secret: str
    folder_id: str
    redirect_uri: str
    refresh_token: str | None


def get_google_drive_settings(*, require_refresh_token: bool = False) -> GoogleDriveSettings | None:
    values = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "folder_id": os.getenv("GOOGLE_DRIVE_FOLDER_ID"),
        "redirect_uri": os.getenv("GOOGLE_OAUTH_REDIRECT_URI"),
    }
    if not any(values.values()):
        return None
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise GoogleDriveConfigurationError(
            "Google Drive is partially configured: " + ", ".join(missing)
        )
    refresh_token = os.getenv("GOOGLE_DRIVE_REFRESH_TOKEN")
    if require_refresh_token and not refresh_token:
        raise GoogleDriveConfigurationError("GOOGLE_DRIVE_REFRESH_TOKEN is not set.")
    return GoogleDriveSettings(refresh_token=refresh_token, **values)  # type: ignore[arg-type]


def build_authorization_url(settings: GoogleDriveSettings, state: str) -> str:
    return f"{AUTHORIZATION_URL}?{urlencode({'client_id': settings.client_id, 'redirect_uri': settings.redirect_uri, 'response_type': 'code', 'scope': DRIVE_FILE_SCOPE, 'access_type': 'offline', 'prompt': 'consent', 'state': state})}"


def _post_form(url: str, values: dict[str, str]) -> dict:
    request = Request(url, data=urlencode(values).encode(), method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GoogleDriveOAuthError("Google OAuth token exchange failed.") from error


def exchange_code(settings: GoogleDriveSettings, code: str) -> str:
    payload = _post_form(TOKEN_URL, {
        "code": code, "client_id": settings.client_id,
        "client_secret": settings.client_secret, "redirect_uri": settings.redirect_uri,
        "grant_type": "authorization_code",
    })
    token = payload.get("refresh_token")
    if not isinstance(token, str) or not token:
        raise GoogleDriveOAuthError("Google did not return a refresh token.")
    return token


def _access_token(settings: GoogleDriveSettings) -> str:
    if not settings.refresh_token:
        raise GoogleDriveConfigurationError("GOOGLE_DRIVE_REFRESH_TOKEN is not set.")
    payload = _post_form(TOKEN_URL, {
        "client_id": settings.client_id, "client_secret": settings.client_secret,
        "refresh_token": settings.refresh_token, "grant_type": "refresh_token",
    })
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise GoogleDriveOAuthError("Google did not return an access token.")
    return token


class GoogleDriveClient:
    def __init__(self, settings: GoogleDriveSettings):
        self._settings = settings

    def _request(self, request: Request) -> bytes:
        request.add_header("Authorization", f"Bearer {_access_token(self._settings)}")
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            raise GoogleDriveOperationError("Google Drive operation failed.") from error

    def upload(self, *, content: bytes, name: str, media_type: str) -> str:
        boundary = "orest-drive-upload-boundary"
        metadata = json.dumps({"name": name, "parents": [self._settings.folder_id]}).encode()
        body = b"\r\n".join((
            f"--{boundary}".encode(), b"Content-Type: application/json; charset=UTF-8", b"", metadata,
            f"--{boundary}".encode(), f"Content-Type: {media_type}".encode(), b"", content,
            f"--{boundary}--".encode(), b"",
        ))
        request = Request(DRIVE_UPLOAD_URL, data=body, method="POST")
        request.add_header("Content-Type", f"multipart/related; boundary={boundary}")
        try:
            payload = json.loads(self._request(request))
            file_id = payload["id"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise GoogleDriveOperationError("Google Drive returned an invalid upload response.") from error
        if not isinstance(file_id, str) or not file_id:
            raise GoogleDriveOperationError("Google Drive returned an invalid file ID.")
        return file_id

    def download(self, file_id: str) -> bytes:
        return self._request(Request(f"{DRIVE_FILES_URL}/{file_id}?alt=media", method="GET"))

    def delete(self, file_id: str) -> None:
        self._request(Request(f"{DRIVE_FILES_URL}/{file_id}", method="DELETE"))
