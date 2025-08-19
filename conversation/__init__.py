"""
Enhanced JARVIS Conversation System

This package provides an improved conversation management system with:
- Better prompt generation
- Optional embedding support (OpenAI, sentence-transformers, or none)
- Enhanced memory management
- Semantic search capabilities
"""

from .core import JARVISConversation
from .memory import MemoryManager
from .embeddings import EmbeddingManager, EmbeddingConfig
from .prompt_optimizer import PromptOptimizer

__all__ = [
    'JARVISConversation',
    'MemoryManager',
    'EmbeddingManager',
    'EmbeddingConfig',
    'PromptOptimizer'
]

__version__ = "2.0.0"