"""
Configuration for the conversation system
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class EmbeddingBackend(Enum):
    """Available embedding backends"""
    NONE = "none"
    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding system"""
    backend: EmbeddingBackend = EmbeddingBackend.NONE
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    similarity_threshold: float = 0.7
    max_results: int = 5
    
    def __post_init__(self):
        """Set default model names based on backend"""
        if self.backend == EmbeddingBackend.OPENAI and not self.model_name:
            self.model_name = "text-embedding-ada-002"
        elif self.backend == EmbeddingBackend.SENTENCE_TRANSFORMERS and not self.model_name:
            self.model_name = "all-MiniLM-L6-v2"


@dataclass
class ConversationConfig:
    """Configuration for conversation management"""
    max_tokens: int = 8000
    history_offset: int = 10250
    prompt_allowance: int = 10
    save_interval: int = 300  # 5 minutes in seconds
    max_memory_entries: int = 100
    memory_summary_length: int = 100
    
    # File paths
    history_folder: str = "History"
    conversation_file: str = "JARVISConversation_history.txt"
    memory_file: str = "memory.txt"
    chat_file: str = "chat.txt"
    embeddings_file: str = "embeddings.json"
    
    # Embedding configuration
    embedding: Optional[EmbeddingConfig] = None
    
    def __post_init__(self):
        """Initialize embedding config if not provided"""
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
    
    def get_file_path(self, filename: str) -> str:
        """Get full path for a conversation file"""
        import os
        return os.path.join(self.history_folder, filename)