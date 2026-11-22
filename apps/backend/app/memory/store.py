"""Conversation history and long-term memory, kept separately for each character.

`SqliteConversationStore` survives restarts (data/memory.sqlite3 by default);
`InMemoryConversationStore` is used when persistence is disabled and in tests.
"""

import itertools
import json
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, cast

from app.ai.base import ChatMessage

Role = Literal["user", "assistant"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS messages_by_character ON messages (character_id, id);
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS long_term_memory (
    character_id TEXT PRIMARY KEY,
    facts TEXT NOT NULL,
    summary TEXT NOT NULL,
    covered_until INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class StoredMessage:
    id: int
    message: ChatMessage


@dataclass(frozen=True)
class LongTermMemory:
    """What a character remembers beyond the recent window."""

    facts: list[str] = field(default_factory=list)
    summary: str = ""
    # Id of the last message already folded into this memory.
    covered_until: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.facts and not self.summary


class ConversationStore(Protocol):
    def recent(self, character_id: str, limit: int) -> list[ChatMessage]:
        """The last `limit` messages of that character, oldest first."""
        ...

    def add(self, character_id: str, messages: list[ChatMessage]) -> None: ...

    def older_than_recent(
        self, character_id: str, keep_recent: int, after_id: int
    ) -> list[StoredMessage]:
        """Messages with id > after_id, excluding the newest `keep_recent`, oldest first."""
        ...

    def get_long_term(self, character_id: str) -> LongTermMemory: ...

    def save_long_term(self, character_id: str, memory: LongTermMemory) -> None: ...

    def clear(self, character_id: str) -> None:
        """Forgets the conversation and the long-term memory of that character."""
        ...

    def get_active_character(self) -> str | None: ...

    def set_active_character(self, character_id: str) -> None: ...

    def get_preferred_model(self) -> str | None: ...

    def set_preferred_model(self, model: str) -> None: ...

    def close(self) -> None: ...


class InMemoryConversationStore:
    """Lost on restart. Each character keeps at most `max_messages`."""

    def __init__(self, max_messages: int = 500) -> None:
        self._messages: defaultdict[str, deque[StoredMessage]] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )
        self._ids = itertools.count(1)
        self._long_term: dict[str, LongTermMemory] = {}
        self._app_values: dict[str, str] = {}

    def recent(self, character_id: str, limit: int) -> list[ChatMessage]:
        return [m.message for m in list(self._messages[character_id])[-limit:]]

    def add(self, character_id: str, messages: list[ChatMessage]) -> None:
        self._messages[character_id].extend(StoredMessage(next(self._ids), m) for m in messages)

    def older_than_recent(
        self, character_id: str, keep_recent: int, after_id: int
    ) -> list[StoredMessage]:
        stored = list(self._messages[character_id])
        older = stored[: max(len(stored) - keep_recent, 0)]
        return [m for m in older if m.id > after_id]

    def get_long_term(self, character_id: str) -> LongTermMemory:
        return self._long_term.get(character_id, LongTermMemory())

    def save_long_term(self, character_id: str, memory: LongTermMemory) -> None:
        self._long_term[character_id] = memory

    def clear(self, character_id: str) -> None:
        self._messages.pop(character_id, None)
        self._long_term.pop(character_id, None)

    def get_active_character(self) -> str | None:
        return self._app_values.get("active_character")

    def set_active_character(self, character_id: str) -> None:
        self._app_values["active_character"] = character_id

    def get_preferred_model(self) -> str | None:
        return self._app_values.get("ai_model")

    def set_preferred_model(self, model: str) -> None:
        self._app_values["ai_model"] = model

    def close(self) -> None:
        pass


class SqliteConversationStore:
    """One local file. Queries are tiny, so they run inline on the event loop."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)

    def recent(self, character_id: str, limit: int) -> list[ChatMessage]:
        rows = self._db.execute(
            "SELECT role, content FROM messages WHERE character_id = ? ORDER BY id DESC LIMIT ?",
            (character_id, limit),
        ).fetchall()
        return [
            ChatMessage(role=cast(Role, role), content=content) for role, content in reversed(rows)
        ]

    def add(self, character_id: str, messages: list[ChatMessage]) -> None:
        with self._db:
            self._db.executemany(
                "INSERT INTO messages (character_id, role, content) VALUES (?, ?, ?)",
                [(character_id, m.role, m.content) for m in messages],
            )

    def older_than_recent(
        self, character_id: str, keep_recent: int, after_id: int
    ) -> list[StoredMessage]:
        rows = self._db.execute(
            "SELECT id, role, content FROM messages "
            "WHERE character_id = ? AND id > ? AND id NOT IN ("
            "  SELECT id FROM messages WHERE character_id = ? ORDER BY id DESC LIMIT ?"
            ") ORDER BY id",
            (character_id, after_id, character_id, keep_recent),
        ).fetchall()
        return [
            StoredMessage(id, ChatMessage(role=cast(Role, role), content=content))
            for id, role, content in rows
        ]

    def get_long_term(self, character_id: str) -> LongTermMemory:
        row = self._db.execute(
            "SELECT facts, summary, covered_until FROM long_term_memory WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return LongTermMemory()
        facts, summary, covered_until = row
        return LongTermMemory(json.loads(facts), summary, covered_until)

    def save_long_term(self, character_id: str, memory: LongTermMemory) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO long_term_memory (character_id, facts, summary, covered_until) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (character_id) DO UPDATE SET "
                "facts = excluded.facts, summary = excluded.summary, "
                "covered_until = excluded.covered_until, updated_at = CURRENT_TIMESTAMP",
                (
                    character_id,
                    json.dumps(memory.facts, ensure_ascii=False),
                    memory.summary,
                    memory.covered_until,
                ),
            )

    def clear(self, character_id: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM messages WHERE character_id = ?", (character_id,))
            self._db.execute("DELETE FROM long_term_memory WHERE character_id = ?", (character_id,))

    def get_active_character(self) -> str | None:
        return self._get_value("active_character")

    def set_active_character(self, character_id: str) -> None:
        self._set_value("active_character", character_id)

    def get_preferred_model(self) -> str | None:
        return self._get_value("ai_model")

    def set_preferred_model(self, model: str) -> None:
        self._set_value("ai_model", model)

    def _get_value(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return cast(str, row[0]) if row else None

    def _set_value(self, key: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO app_state (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def close(self) -> None:
        self._db.close()
