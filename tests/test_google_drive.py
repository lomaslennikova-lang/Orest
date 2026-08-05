from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.google_drive import (
    DRIVE_FILE_SCOPE,
    GoogleDriveConfigurationError,
    build_authorization_url,
    get_google_drive_settings,
)


class GoogleDriveSettingsTests(unittest.TestCase):
    def test_missing_configuration_keeps_drive_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(get_google_drive_settings())

    def test_partial_configuration_is_rejected(self):
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "client"}, clear=True):
            with self.assertRaises(GoogleDriveConfigurationError):
                get_google_drive_settings()

    def test_authorization_url_has_minimal_scope_and_state(self):
        environment = {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "GOOGLE_DRIVE_FOLDER_ID": "folder-id",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://orest.onrender.com/api/admin/google-drive/callback",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = get_google_drive_settings()
            assert settings is not None
            query = parse_qs(urlparse(build_authorization_url(settings, "csrf-state")).query)
        self.assertEqual(query["scope"], [DRIVE_FILE_SCOPE])
        self.assertEqual(query["state"], ["csrf-state"])
        self.assertEqual(query["access_type"], ["offline"])
