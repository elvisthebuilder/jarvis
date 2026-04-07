"""SQLite-based memory store for Jarvis.

Stores interactions, learned preferences, detected patterns,
and persistent context across sessions.
"""

import logging
import aiosqlite
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_input TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    tools_used TEXT,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    source TEXT DEFAULT 'explicit',
    confidence REAL DEFAULT 1.0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    description TEXT NOT NULL,
    data TEXT,
    frequency INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    fire_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fired INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_context_key ON context(key);
"""


class MemoryStore:
    """Async SQLite store for Jarvis's persistent memory.
    
    Handles interactions, preferences, patterns, and context
    with async access via aiosqlite.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Connect to the database and create tables if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info(f"Memory store initialized at {self.db_path}")

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ── Interactions ──────────────────────────────────────────

    async def log_interaction(
        self,
        user_input: str,
        assistant_response: str,
        tools_used: list[str] | None = None,
        session_id: str | None = None,
    ):
        """Log a user interaction for learning and history."""
        await self._db.execute(
            "INSERT INTO interactions (timestamp, user_input, assistant_response, tools_used, session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                user_input,
                assistant_response,
                ",".join(tools_used) if tools_used else None,
                session_id,
            ),
        )
        await self._db.commit()

    async def get_recent_interactions(self, limit: int = 10) -> list[dict]:
        """Get the most recent interactions."""
        cursor = await self._db.execute(
            "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ── Preferences ──────────────────────────────────────────

    async def set_preference(self, key: str, value: str, source: str = "explicit", confidence: float = 1.0):
        """Set or update a user preference."""
        await self._db.execute(
            "INSERT INTO preferences (key, value, source, confidence, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?, source=?, confidence=?, updated_at=?",
            (
                key, value, source, confidence, datetime.now().isoformat(),
                value, source, confidence, datetime.now().isoformat(),
            ),
        )
        await self._db.commit()

    async def get_preference(self, key: str) -> str | None:
        """Get a specific preference value."""
        cursor = await self._db.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def get_all_preferences(self) -> dict[str, str]:
        """Get all preferences as a dict."""
        cursor = await self._db.execute("SELECT key, value FROM preferences")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ── Context ──────────────────────────────────────────────

    async def set_context(self, key: str, value: str):
        """Set a persistent context value (e.g., user's name, commonly used apps)."""
        await self._db.execute(
            "INSERT INTO context (key, value, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
            (key, value, datetime.now().isoformat(), value, datetime.now().isoformat()),
        )
        await self._db.commit()

    async def get_context(self, key: str) -> str | None:
        """Get a persistent context value."""
        cursor = await self._db.execute(
            "SELECT value FROM context WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def get_all_context(self) -> dict[str, str]:
        """Get all context values as a dict."""
        cursor = await self._db.execute("SELECT key, value FROM context")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ── Patterns ─────────────────────────────────────────────

    async def record_pattern(self, pattern_type: str, description: str, data: str | None = None):
        """Record or update a usage pattern."""
        now = datetime.now().isoformat()
        
        # Check if this pattern already exists
        cursor = await self._db.execute(
            "SELECT id, frequency FROM patterns WHERE pattern_type = ? AND description = ?",
            (pattern_type, description),
        )
        row = await cursor.fetchone()
        
        if row:
            await self._db.execute(
                "UPDATE patterns SET frequency = frequency + 1, last_seen = ?, data = COALESCE(?, data) "
                "WHERE id = ?",
                (now, data, row["id"]),
            )
        else:
            await self._db.execute(
                "INSERT INTO patterns (pattern_type, description, data, last_seen, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (pattern_type, description, data, now, now),
            )
        await self._db.commit()

    async def get_frequent_patterns(self, min_frequency: int = 3) -> list[dict]:
        """Get patterns that occur frequently."""
        cursor = await self._db.execute(
            "SELECT * FROM patterns WHERE frequency >= ? ORDER BY frequency DESC",
            (min_frequency,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ── Stats ────────────────────────────────────────────────

    async def get_interaction_count(self) -> int:
        """Get the total number of interactions."""
        cursor = await self._db.execute("SELECT COUNT(*) as count FROM interactions")
        row = await cursor.fetchone()
        return row["count"]
