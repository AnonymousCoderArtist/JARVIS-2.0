"""Semantic memory system with embeddings"""

from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
import numpy as np


@dataclass
class MemoryEntry:
    """A single memory entry"""
    content: str
    importance: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    embedding: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)


class SemanticMemory:
    """Semantic memory system with embeddings"""

    def __init__(self, embedding_backend: Optional[str] = None):
        self.entries: List[MemoryEntry] = []
        self.embedding_backend = embedding_backend
        self._embedding_model = None
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        """Initialize the embedding backend"""
        if self.embedding_backend == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                print("⚠ sentence-transformers not installed. Install with: pip install sentence-transformers")
                self.embedding_backend = None

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text"""
        if self._embedding_model:
            return self._embedding_model.encode(text)
        return None

    async def add(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add a memory entry

        Args:
            content: Memory content
            importance: Importance score (0.0 to 1.0)
            metadata: Optional metadata dictionary

        Returns:
            Memory entry ID (index in list)
        """
        embedding = self._get_embedding(content) if self.embedding_backend else None
        
        entry = MemoryEntry(
            content=content,
            importance=importance,
            embedding=embedding,
            metadata=metadata or {}
        )
        
        self.entries.append(entry)
        return str(len(self.entries) - 1)

    async def retrieve(
        self,
        query: str,
        limit: int = 5,
        importance_threshold: float = 0.0
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memories using semantic search

        Args:
            query: Search query
            limit: Maximum number of results
            importance_threshold: Minimum importance score

        Returns:
            List of relevant memory entries
        """
        if not self.entries:
            return []

        # Filter by importance threshold
        filtered_entries = [
            entry for entry in self.entries
            if entry.importance >= importance_threshold
        ]

        if not filtered_entries:
            return []

        # If no embedding backend, return most recent entries
        if not self.embedding_backend:
            return sorted(filtered_entries, key=lambda x: x.timestamp, reverse=True)[:limit]

        # Use semantic search
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return sorted(filtered_entries, key=lambda x: x.timestamp, reverse=True)[:limit]

        # Calculate similarities
        scored_entries = []
        for entry in filtered_entries:
            if entry.embedding is not None:
                similarity = self._cosine_similarity(query_embedding, entry.embedding)
                # Combine similarity with importance
                score = (similarity * 0.7) + (entry.importance * 0.3)
                scored_entries.append((entry, score))

        # Sort by score and return top results
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored_entries[:limit]]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        return dot_product / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

    async def cleanup(self, threshold: float = 0.3, max_entries: Optional[int] = None):
        """
        Clean up low-importance memories

        Args:
            threshold: Importance threshold below which to remove entries
            max_entries: Maximum number of entries to keep (keeps most recent)
        """
        # Remove low importance entries
        self.entries = [
            entry for entry in self.entries
            if entry.importance >= threshold
        ]

        # If max_entries specified, keep only the most recent
        if max_entries and len(self.entries) > max_entries:
            self.entries = sorted(self.entries, key=lambda x: x.timestamp, reverse=True)[:max_entries]

    async def update_importance(self, entry_id: str, new_importance: float):
        """
        Update importance of a memory entry

        Args:
            entry_id: Memory entry ID (index)
            new_importance: New importance score
        """
        try:
            idx = int(entry_id)
            if 0 <= idx < len(self.entries):
                self.entries[idx].importance = new_importance
        except (ValueError, IndexError):
            pass

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        if not self.entries:
            return {
                "total_entries": 0,
                "avg_importance": 0.0,
                "with_embeddings": 0
            }

        avg_importance = sum(e.importance for e in self.entries) / len(self.entries)
        with_embeddings = sum(1 for e in self.entries if e.embedding is not None)

        return {
            "total_entries": len(self.entries),
            "avg_importance": avg_importance,
            "with_embeddings": with_embeddings,
            "embedding_backend": self.embedding_backend
        }

    def clear(self):
        """Clear all memory entries"""
        self.entries = []
