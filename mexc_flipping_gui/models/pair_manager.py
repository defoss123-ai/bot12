"""Pair management with SQLite persistence and in-memory cache."""

from __future__ import annotations

import sqlite3
from typing import Any


class PairManager:
    def __init__(self, db_connection: sqlite3.Connection, logger) -> None:
        self.db_connection = db_connection
        self.logger = logger
        self.pairs: dict[str, dict[str, Any]] = {}
        self.load_pairs()

    def load_pairs(self) -> dict[str, dict[str, Any]]:
        rows = self.db_connection.execute(
            "SELECT symbol, enabled, leverage, tp_percent, sl_percent, cancel_time, created_at, updated_at FROM pairs"
        ).fetchall()
        self.pairs = {
            row["symbol"]: {
                "symbol": row["symbol"],
                "enabled": bool(row["enabled"]),
                "leverage": int(row["leverage"]),
                "tp_percent": float(row["tp_percent"]),
                "sl_percent": float(row["sl_percent"]),
                "cancel_time": int(row["cancel_time"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }
        self.logger.info("Loaded %d trading pairs", len(self.pairs))
        return self.pairs

    def add_pair(
        self,
        symbol: str,
        leverage: int,
        tp_percent: float,
        sl_percent: float,
        cancel_time: int,
        enabled: bool = True,
    ) -> None:
        symbol = symbol.strip().upper()
        self._validate_pair(leverage, tp_percent, sl_percent, cancel_time)
        with self.db_connection:
            self.db_connection.execute(
                """
                INSERT INTO pairs (symbol, enabled, leverage, tp_percent, sl_percent, cancel_time, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(symbol) DO UPDATE SET
                    enabled=excluded.enabled,
                    leverage=excluded.leverage,
                    tp_percent=excluded.tp_percent,
                    sl_percent=excluded.sl_percent,
                    cancel_time=excluded.cancel_time,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (symbol, int(enabled), leverage, tp_percent, sl_percent, cancel_time),
            )
        self.logger.info("Pair %s saved (enabled=%s)", symbol, enabled)
        self.load_pairs()

    def remove_pair(self, symbol: str) -> None:
        symbol = symbol.strip().upper()
        with self.db_connection:
            cursor = self.db_connection.execute("DELETE FROM pairs WHERE symbol = ?", (symbol,))
        if cursor.rowcount == 0:
            self.logger.warning("Pair %s was not found for deletion", symbol)
        else:
            self.logger.info("Pair %s deleted", symbol)
        self.pairs.pop(symbol, None)

    def update_pair(self, symbol: str, **kwargs: Any) -> None:
        symbol = symbol.strip().upper()
        allowed = {"enabled", "leverage", "tp_percent", "sl_percent", "cancel_time"}
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            self.logger.warning("No valid fields provided for %s update", symbol)
            return

        leverage = int(update_data.get("leverage", self.pairs.get(symbol, {}).get("leverage", 10)))
        tp_percent = float(update_data.get("tp_percent", self.pairs.get(symbol, {}).get("tp_percent", 2.0)))
        sl_percent = float(update_data.get("sl_percent", self.pairs.get(symbol, {}).get("sl_percent", 1.0)))
        cancel_time = int(update_data.get("cancel_time", self.pairs.get(symbol, {}).get("cancel_time", 60)))
        self._validate_pair(leverage, tp_percent, sl_percent, cancel_time)

        assignments = ", ".join([f"{field} = ?" for field in update_data]) + ", updated_at = CURRENT_TIMESTAMP"
        params = [int(v) if field == "enabled" else v for field, v in update_data.items()] + [symbol]
        with self.db_connection:
            cursor = self.db_connection.execute(
                f"UPDATE pairs SET {assignments} WHERE symbol = ?",
                params,
            )
        if cursor.rowcount == 0:
            self.logger.warning("Pair %s not found during update", symbol)
            return
        self.logger.info("Pair %s updated: %s", symbol, update_data)
        self.load_pairs()

    def enable_pair(self, symbol: str) -> None:
        self.update_pair(symbol, enabled=1)
        self.logger.info("Pair %s enabled", symbol.upper())

    def disable_pair(self, symbol: str) -> None:
        self.update_pair(symbol, enabled=0)
        self.logger.info("Pair %s disabled", symbol.upper())

    def get_active_pairs(self) -> list[str]:
        return [symbol for symbol, settings in self.pairs.items() if settings.get("enabled")]

    def get_pair_settings(self, symbol: str) -> dict[str, Any] | None:
        return self.pairs.get(symbol.strip().upper())

    def _validate_pair(self, leverage: int, tp_percent: float, sl_percent: float, cancel_time: int) -> None:
        if not 1 <= int(leverage) <= 125:
            raise ValueError("Leverage must be between 1 and 125")
        if float(tp_percent) <= 0:
            raise ValueError("TP percent must be > 0")
        if float(sl_percent) <= 0:
            raise ValueError("SL percent must be > 0")
        if int(cancel_time) < 0:
            raise ValueError("Cancel time must be >= 0")
