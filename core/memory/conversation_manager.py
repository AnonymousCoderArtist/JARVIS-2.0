"""Conversation manager for chat history and context"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


@dataclass
class Message:
    """A single message in a conversation"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    token_count: int = 0  # Actual or estimated token count
    is_summary: bool = False


class ConversationManager:
    """Manages conversation history and context with auto-summarization"""

    def __init__(
        self,
        max_history: int = 50,
        context_threshold: float = 0.75,
        summarization_callback: Callable | None = None,
        model: str | None = None
    ):
        self.messages: list[Message] = []
        self.max_history = max_history
        self.session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.context_threshold = context_threshold  # Threshold for auto-summarization (0.75 = 75%)
        self.summarization_callback = summarization_callback  # Callback to generate summaries
        self.max_context_tokens: int = 200000  # Default, can be updated per model
        self.model = model or "cl100k_base"  # Default tiktoken encoding
        self._summary_cache: list[Message] = []  # Store previous summaries

        # Initialize tiktoken if available
        self.encoding = None
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.get_encoding(self.model)
            except Exception:
                # Fallback to cl100k_base if model not found
                try:
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    pass

    def _count_tokens(self, text: str, native_count: int | None = None) -> int:
        """
        Count tokens for text using native count if provided, otherwise estimate with tiktoken

        Args:
            text: Text to count tokens for
            native_count: Optional native token count from LLM response

        Returns:
            Token count
        """
        # Use native count if provided (most accurate)
        if native_count is not None:
            return native_count

        # Use tiktoken if available
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass

        # Fallback to simple estimation: 1 token ≈ 4 characters
        return len(text) // 4

    def set_max_context_tokens(self, max_tokens: int):
        """
        Set the maximum context tokens for the current model

        Args:
            max_tokens: Maximum context tokens
        """
        self.max_context_tokens = max_tokens

    def get_estimated_tokens(self) -> int:
        """
        Get total tokens in conversation

        Returns:
            Total token count
        """
        return sum(m.token_count for m in self.messages)

    def get_context_usage_ratio(self) -> float:
        """
        Get the current context usage ratio (0.0 to 1.0)

        Returns:
            Ratio of used tokens to max context
        """
        total_tokens = self.get_estimated_tokens()
        if self.max_context_tokens == 0:
            return 0.0
        return total_tokens / self.max_context_tokens

    def add_message(self, role: str, content: str, metadata: dict | None = None, token_count: int | None = None):
        """
        Add a message to the conversation

        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata
            token_count: Optional native token count from LLM response
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
            token_count=self._count_tokens(content, token_count),
            is_summary=metadata.get('is_summary', False) if metadata else False
        )
        self.messages.append(message)

        # Check if we need to summarize
        if self._should_summarize():
            asyncio.create_task(self._summarize_history())

        self._trim_history()

    def _should_summarize(self) -> bool:
        """
        Check if conversation should be summarized based on context usage

        Returns:
            True if summarization is needed
        """
        # Don't summarize if we have a callback
        if not self.summarization_callback:
            return False

        # Check if context usage exceeds threshold
        usage_ratio = self.get_context_usage_ratio()
        return usage_ratio >= self.context_threshold

    async def _summarize_history(self):
        """
        Summarize conversation history when context threshold is reached
        """
        if not self.summarization_callback:
            return

        # Separate system messages from conversation
        system_messages = [m for m in self.messages if m.role == 'system']
        conversation_messages = [m for m in self.messages if m.role != 'system']

        # Don't summarize if there's not enough to summarize
        if len(conversation_messages) < 4:
            return

        # Get messages to summarize (all except the most recent 2-3 to maintain context)
        messages_to_summarize = conversation_messages[:-3]
        recent_messages = conversation_messages[-3:]

        if not messages_to_summarize:
            return

        # Convert to format for summarization
        summary_input = [
            {
                "role": m.role,
                "content": m.content
            }
            for m in messages_to_summarize
        ]

        try:
            # Generate summary using the callback
            summary_result = await self.summarization_callback(summary_input)

            # Handle both string and tuple returns
            if isinstance(summary_result, tuple):
                summary, token_count = summary_result
            else:
                summary = summary_result
                token_count = None

            # Create a summary message (as assistant role, not system)
            summary_message = Message(
                role="assistant",
                content=f"[Summary of previous conversation]\n{summary}",
                timestamp=datetime.now(),
                metadata={"is_summary": True, "summarized_count": len(messages_to_summarize)},
                token_count=self._count_tokens(summary, token_count),
                is_summary=True
            )

            # Replace old messages with summary (keep system messages)
            self.messages = system_messages + [summary_message] + recent_messages

        except Exception as e:
            # If summarization fails, just trim normally
            print(f"Summarization failed: {e}")

    def _trim_history(self):
        """Trim history to max_history size"""
        if len(self.messages) > self.max_history:
            # Keep system messages and most recent messages
            system_messages = [m for m in self.messages if m.role == 'system']
            other_messages = [m for m in self.messages if m.role != 'system']

            # Keep most recent non-system messages
            recent_messages = other_messages[-(self.max_history - len(system_messages)):]

            self.messages = system_messages + recent_messages

    def get_messages(self, limit: int | None = None) -> list[dict]:
        """
        summary_count = sum(1 for m in self.messages if m.metadata.get('is_summary', False))
        Get messages in LLM format

        Args:
            limit: Maximum number of messages to return

        Retu"system_messagesr: ns:m_count,
            "sumaryummar_count,
            "eimatd_tokens": self.get_estiatedtokens(),
            "ntext_sage_ratio": self.get_cotext_usage_raio()
            List of message dictionaries
        """
        messages = self.messages[-limit:] if limit else self.messages
        return [
            {
                "role": m.role,
                "content": m.content
            }
            for m in messages
        ]

    def get_context_window(self, max_tokens: int = 8000) -> list[dict]:
        """
        Get messages that fit within a token limit

        Args:
            max_tokens: Maximum tokens to include

        Returns:
            List of message dictionaries
        """
        # Simple estimation: 1 token ≈ 4 characters
        messages = []
        total_chars = 0

        for message in reversed(self.messages):
            message_chars = len(message.content)
            if total_chars + message_chars > max_tokens * 4:
                break
            messages.insert(0, {
                "role": message.role,
                "content": message.content
            })
            total_chars += message_chars

        return messages

    def get_last_user_message(self) -> str | None:
        """Get the last user message"""
        for message in reversed(self.messages):
            if message.role == 'user':
                return message.content
        return None

    def get_last_assistant_message(self) -> str | None:
        """Get the last assistant message"""
        for message in reversed(self.messages):
            if message.role == 'assistant':
                return message.content
        return None

    def clear(self):
        """Clear all messages except system messages"""
        self.messages = [m for m in self.messages if m.role == 'system']

    def get_stats(self) -> dict:
        """Get conversation statistics"""
        user_count = sum(1 for m in self.messages if m.role == 'user')
        assistant_count = sum(1 for m in self.messages if m.role == 'assistant')
        system_count = sum(1 for m in self.messages if m.role == 'system')
        summary_count = sum(1 for m in self.messages if m.is_summary)

        return {
            "total_messages": len(self.messages),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
            "system_messages": system_count,
            "summary_messages": summary_count,
            "total_tokens": sum(m.token_count for m in self.messages),
            "context_usage_ratio": self.get_context_usage_ratio(),
            "session_id": self.session_id
        }

    def export(self) -> list[dict]:
        """Export conversation history"""
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "metadata": m.metadata
            }
            for m in self.messages
        ]

    def import_history(self, history: list[dict]):
        """Import conversation history"""
        for entry in history:
            self.add_message(
                role=entry.get("role", "user"),
                content=entry.get("content", ""),
                metadata=entry.get("metadata", {})
            )
