from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ApiConfigStore:
    def __init__(self, path: str = "config.json") -> None:
        self.path = Path(path)

    def save_keys(self, api_key: str, api_secret: str) -> None:
        self.path.write_text(
            json.dumps({"api_key": api_key, "api_secret": api_secret}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_keys(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.path.exists():
            logger.error("API keys missing: config.json not found")
            return None, None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to read API keys from config.json: %s", exc)
            return None, None

        api_key = (data.get("api_key") or "").strip()
        api_secret = (data.get("api_secret") or "").strip()
        if api_key and api_secret:
            logger.info("API keys loaded successfully")
            return api_key, api_secret

        logger.error("API keys missing in config.json")
        return None, None
