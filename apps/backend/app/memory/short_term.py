from collections import deque

from app.ai.base import ChatMessage


class ShortTermMemory:
    """Rolling window of the most recent turns. Persistent memory comes in a later phase."""

    def __init__(self, max_messages: int) -> None:
        self._messages: deque[ChatMessage] = deque(maxlen=max_messages)

    def add(self, message: ChatMessage) -> None:
        self._messages.append(message)

    def get_recent_context(self) -> list[ChatMessage]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
