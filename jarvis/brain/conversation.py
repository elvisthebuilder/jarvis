"""Conversation and context management for Jarvis sessions."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Maximum messages to keep in active context
MAX_CONTEXT_MESSAGES = 40


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # "user", "assistant", "tool", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list | None = None
    tool_name: str | None = None


class ConversationManager:
    """Manages conversation context with sliding window and compression.
    
    Keeps a rolling window of recent messages to stay within token limits,
    while preserving important context through summarization.
    """

    def __init__(self, max_messages: int = MAX_CONTEXT_MESSAGES):
        self.max_messages = max_messages
        self.messages: list[Message] = []
        self.session_start = datetime.now()
        self._summary: str | None = None

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append(Message(role="user", content=content))
        self._trim_if_needed()

    def add_assistant_message(self, content: str, tool_calls: list | None = None) -> None:
        """Add an assistant response to the conversation."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))
        self._trim_if_needed()

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """Add a tool execution result to the conversation."""
        self.messages.append(Message(
            role="tool",
            content=result,
            tool_name=tool_name,
        ))

    def get_messages_for_api(self) -> list[dict]:
        """Get messages formatted for the Ollama/Gemini API.
        
        Returns:
            List of message dicts with role and content.
        """
        api_messages = []

        # Include summary of older context if available
        if self._summary:
            api_messages.append({
                "role": "system",
                "content": f"[Previous conversation context: {self._summary}]",
            })

        for msg in self.messages:
            api_msg = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                api_msg["tool_calls"] = msg.tool_calls
            if msg.tool_name:
                api_msg["name"] = msg.tool_name
            api_messages.append(api_msg)

        return api_messages

    def get_recent_context_summary(self, n: int = 5) -> str | None:
        """Get a brief summary of recent interactions for prompt injection.
        
        Args:
            n: Number of recent user messages to summarize.
            
        Returns:
            Brief context string or None if no history.
        """
        user_messages = [m for m in self.messages if m.role == "user"]
        if not user_messages:
            return None

        recent = user_messages[-n:]
        topics = [m.content[:80] for m in recent]
        return f"Recent requests: {'; '.join(topics)}"

    def clear(self) -> None:
        """Clear conversation history and start fresh."""
        self.messages.clear()
        self._summary = None
        self.session_start = datetime.now()

    def _trim_if_needed(self) -> None:
        """Trim conversation to stay within limits, preserving a summary."""
        if len(self.messages) <= self.max_messages:
            return

        # Summarize the oldest messages before discarding
        overflow = self.messages[: len(self.messages) - self.max_messages]
        user_msgs = [m.content[:60] for m in overflow if m.role == "user"]
        if user_msgs:
            self._summary = f"Earlier in this session, Sir discussed: {'; '.join(user_msgs)}"

        # Keep only the most recent messages
        self.messages = self.messages[-self.max_messages:]
        logger.debug(f"Trimmed conversation to {self.max_messages} messages")

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def is_empty(self) -> bool:
        return len(self.messages) == 0
