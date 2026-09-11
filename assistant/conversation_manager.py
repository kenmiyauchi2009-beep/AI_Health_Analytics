from __future__ import annotations

from assistant.chat_message import ChatMessage


class ConversationManager:
    """Stores chat turns for the current Streamlit session."""

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    @property
    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

    def add_user(self, content: str) -> None:
        self._messages.append(ChatMessage(role="user", content=content))

    def add_assistant(self, content: str) -> None:
        self._messages.append(ChatMessage(role="assistant", content=content))

    def clear(self) -> None:
        self._messages.clear()
