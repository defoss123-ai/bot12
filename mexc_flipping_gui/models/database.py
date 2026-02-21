"""Database helpers for the MEXC flipping bot."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

PAIRS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    enabled INTEGER DEFAULT 1,
    leverage INTEGER DEFAULT 10,
    tp_percent REAL DEFAULT 2.0,
    sl_percent REAL DEFAULT 1.0,
    cancel_time INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

LOGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT,
    message TEXT
);
"""

POSITIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT CHECK(side IN ('LONG','SHORT')),
    entry_price REAL,
    quantity REAL,
    status TEXT DEFAULT 'open',
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);
"""

ORDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    side TEXT,
    type TEXT,
    price REAL,
    amount REAL,
    status TEXT,
    created_at TIMESTAMP,
    cancel_after INTEGER
);
"""


def init_db(db_path: str = "trading_bot.db") -> sqlite3.Connection:
    """Initialize SQLite database and return connection."""
    db_file = Path(db_path)
    if db_file.parent and not db_file.parent.exists():
        db_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing database at %s", db_file)
    connection = sqlite3.connect(db_file)
    connection.row_factory = sqlite3.Row

    with connection:
        connection.execute(SETTINGS_SCHEMA)
        connection.execute(PAIRS_SCHEMA)
        connection.execute(LOGS_SCHEMA)
        connection.execute(POSITIONS_SCHEMA)
        connection.execute(ORDERS_SCHEMA)

    logger.info("Database initialization complete")
    return connection


class Database:
    """Small helper wrapper around sqlite3.Connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> sqlite3.Cursor:
        logger.debug("DB execute: %s | params=%s", query, params)
        with self.connection:
            return self.connection.execute(query, tuple(params or ()))

    def fetch_one(self, query: str, params: Optional[Iterable[Any]] = None) -> Optional[sqlite3.Row]:
        logger.debug("DB fetch_one: %s | params=%s", query, params)
        cursor = self.connection.execute(query, tuple(params or ()))
        return cursor.fetchone()

    def fetch_all(self, query: str, params: Optional[Iterable[Any]] = None) -> list[sqlite3.Row]:
        logger.debug("DB fetch_all: %s | params=%s", query, params)
        cursor = self.connection.execute(query, tuple(params or ()))
        return cursor.fetchall()
