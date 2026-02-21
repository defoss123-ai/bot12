"""Encryption utilities for sensitive settings."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def get_or_create_fernet_key(key_path: str = "master.key") -> Fernet:
    """Load existing Fernet key from disk or create a new one."""
    key_file = Path(key_path)

    if key_file.exists():
        logger.info("Loading existing Fernet key from %s", key_file)
        key = key_file.read_bytes()
        return Fernet(key)

    logger.info("Generating new Fernet key at %s", key_file)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    os.chmod(key_file, 0o600)
    return Fernet(key)


class EncryptedSettings:
    """Store/retrieve encrypted settings in the settings table."""

    API_KEY_FIELD = "api_key"
    API_SECRET_FIELD = "api_secret"

    def __init__(self, db_connection: sqlite3.Connection, fernet: Fernet) -> None:
        self.db_connection = db_connection
        self.fernet = fernet

    def set_api_keys(self, api_key: str, secret: str) -> None:
        """Encrypt and persist API credentials."""
        logger.info("Saving encrypted API keys")
        encrypted_api_key = self.fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")
        encrypted_secret = self.fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

        with self.db_connection:
            self.db_connection.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (self.API_KEY_FIELD, encrypted_api_key),
            )
            self.db_connection.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (self.API_SECRET_FIELD, encrypted_secret),
            )

    def get_api_keys(self) -> Tuple[Optional[str], Optional[str]]:
        """Read and decrypt API credentials."""
        logger.info("Loading encrypted API keys")

        api_key_row = self.db_connection.execute(
            "SELECT value FROM settings WHERE key = ?", (self.API_KEY_FIELD,)
        ).fetchone()
        secret_row = self.db_connection.execute(
            "SELECT value FROM settings WHERE key = ?", (self.API_SECRET_FIELD,)
        ).fetchone()

        if not api_key_row or not secret_row:
            logger.info("API keys are not configured")
            return None, None

        try:
            api_key = self.fernet.decrypt(api_key_row["value"].encode("utf-8")).decode("utf-8")
            secret = self.fernet.decrypt(secret_row["value"].encode("utf-8")).decode("utf-8")
            return api_key, secret
        except Exception:
            logger.exception("Failed to decrypt API keys")
            return None, None
