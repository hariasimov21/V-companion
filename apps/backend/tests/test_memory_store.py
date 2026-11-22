from pathlib import Path

from app.ai.base import ChatMessage
from app.memory.store import InMemoryConversationStore, SqliteConversationStore


def msg(role: str, text: str) -> ChatMessage:
    return ChatMessage.model_validate({"role": role, "content": text})


def test_sqlite_store_keeps_characters_apart_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "memory.sqlite3"
    store = SqliteConversationStore(path)
    store.add("akari", [msg("user", "hola"), msg("assistant", "hola!")])
    store.add("mimi", [msg("user", "miau")])
    store.set_active_character("mimi")
    store.close()

    reopened = SqliteConversationStore(path)
    assert [m.content for m in reopened.recent("akari", 10)] == ["hola", "hola!"]
    assert [m.content for m in reopened.recent("mimi", 10)] == ["miau"]
    assert reopened.recent("nobody", 10) == []
    assert reopened.get_active_character() == "mimi"
    reopened.close()


def test_recent_returns_the_newest_messages_oldest_first(tmp_path: Path) -> None:
    for store in (SqliteConversationStore(tmp_path / "m.sqlite3"), InMemoryConversationStore()):
        store.add("akari", [msg("user", str(i)) for i in range(5)])
        assert [m.content for m in store.recent("akari", 3)] == ["2", "3", "4"]
        store.clear("akari")
        assert store.recent("akari", 3) == []
        store.close()


def test_store_rejects_sql_injection_like_ids(tmp_path: Path) -> None:
    store = SqliteConversationStore(tmp_path / "m.sqlite3")
    store.add("x'; DROP TABLE messages; --", [msg("user", "hola")])
    assert [m.content for m in store.recent("x'; DROP TABLE messages; --", 1)] == ["hola"]
    store.close()
