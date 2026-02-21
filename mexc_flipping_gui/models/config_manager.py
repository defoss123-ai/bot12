"""Global settings manager."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage global JSON settings from the settings table."""

    DEFAULTS = {
        "lookback": 20,
        "volume_multiplier": 1.5,
        "check_interval": 60,
        "risk_per_trade": 5.0,
    }

    def __init__(self, db_connection: sqlite3.Connection) -> None:
        self.db_connection = db_connection
        self.cache: dict[str, Any] = {}
        self.load_all()
        self._ensure_defaults()

    def get(self, key: str, default: Any = None) -> Any:
        """Return deserialized setting value."""
        if key in self.cache:
            return self.cache[key]

        row = self.db_connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()

        if row is None:
            return default

        value = self._deserialize(row["value"])
        self.cache[key] = value
        logger.debug("Loaded setting %s=%s", key, value)
        return value

    def set(self, key: str, value: Any) -> None:
        """Serialize and persist setting value."""
        serialized = json.dumps(value)
        logger.info("Saving setting %s=%s", key, value)

        with self.db_connection:
            self.db_connection.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, serialized),
            )

        self.cache[key] = value

    def load_all(self) -> dict[str, Any]:
        """Load all settings from database into in-memory cache."""
        rows = self.db_connection.execute("SELECT key, value FROM settings").fetchall()
        self.cache = {row["key"]: self._deserialize(row["value"]) for row in rows}
        logger.info("Loaded %d settings into cache", len(self.cache))
        return self.cache

    def _ensure_defaults(self) -> None:
        for key, value in self.DEFAULTS.items():
            if self.get(key) is None:
                self.set(key, value)

    @staticmethod
    def _deserialize(value: str) -> Any:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
