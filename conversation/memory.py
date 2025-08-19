"""
Enhanced memory management system for JARVIS
"""
import json
import logging
import os
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .embeddings import EmbeddingManager
from .config import ConversationConfig


@dataclass
class MemoryEntry:
    """Single memory entry"""
    id: str
    content: str
    timestamp: float
    metadata: Dict[str, Any]
    importance: float = 0.5  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'importance': self.importance
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            content=data['content'],
            timestamp=data['timestamp'],
            metadata=data.get('metadata', {}),
            importance=data.get('importance', 0.5)
        )


class MemoryManager:
    """Enhanced memory management with semantic search capabilities"""
    
    def __init__(self, config: ConversationConfig, embedding_manager: Optional[EmbeddingManager] = None):
        self.config = config
        self.embedding_manager = embedding_manager
        self.memory_file = config.get_file_path(config.memory_file)
        self.memories: List[MemoryEntry] = []
        self.load_memories()
    
    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None, importance: float = 0.5) -> str:
        """Add a new memory entry"""
        import uuid
        
        memory_id = str(uuid.uuid4())
        timestamp = time.time()
        
        memory = MemoryEntry(
            id=memory_id,
            content=content,
            timestamp=timestamp,
            metadata=metadata or {},
            importance=importance
        )
        
        self.memories.append(memory)
        
        # Add to embedding database if available
        if self.embedding_manager:
            metadata_dict = metadata or {}
            embedding_metadata = {
                'type': 'memory',
                'timestamp': timestamp,
                'importance': importance
            }
            embedding_metadata.update(metadata_dict)
            
            self.embedding_manager.add_text(
                text_id=memory_id,
                text=content,
                metadata=embedding_metadata
            )
        
        self._cleanup_old_memories()
        self.save_memories()
        
        return memory_id
    
    def search_memories(self, query: str, max_results: Optional[int] = None) -> List[MemoryEntry]:
        """Search memories using semantic similarity or keyword matching"""
        max_results = max_results or self.config.embedding.max_results
        
        # If embedding manager is available, use semantic search
        if self.embedding_manager:
            similar_entries = self.embedding_manager.search_similar(query, max_results)
            memory_ids = [entry[0] for entry in similar_entries]
            return [m for m in self.memories if m.id in memory_ids]
        
        # Fallback to keyword search
        return self._keyword_search(query, max_results)
    
    def _keyword_search(self, query: str, max_results: int) -> List[MemoryEntry]:
        """Simple keyword-based search fallback"""
        query_words = query.lower().split()
        matches = []
        
        for memory in self.memories:
            content_lower = memory.content.lower()
            score = sum(1 for word in query_words if word in content_lower)
            if score > 0:
                matches.append((memory, score))
        
        # Sort by score and importance
        matches.sort(key=lambda x: (x[1], x[0].importance), reverse=True)
        return [match[0] for match in matches[:max_results]]
    
    def get_recent_memories(self, limit: int = 10) -> List[MemoryEntry]:
        """Get most recent memories"""
        sorted_memories = sorted(self.memories, key=lambda m: m.timestamp, reverse=True)
        return sorted_memories[:limit]
    
    def get_important_memories(self, limit: int = 10) -> List[MemoryEntry]:
        """Get most important memories"""
        sorted_memories = sorted(self.memories, key=lambda m: m.importance, reverse=True)
        return sorted_memories[:limit]
    
    def update_memory(self, memory_id: str, content: Optional[str] = None, 
                     metadata: Optional[Dict[str, Any]] = None, 
                     importance: Optional[float] = None) -> bool:
        """Update an existing memory"""
        for memory in self.memories:
            if memory.id == memory_id:
                if content is not None:
                    memory.content = content
                if metadata is not None:
                    memory.metadata.update(metadata)
                if importance is not None:
                    memory.importance = importance
                
                # Update embedding if available
                if self.embedding_manager and content is not None:
                    metadata_dict = memory.metadata.copy()
                    embedding_metadata = {
                        'type': 'memory',
                        'timestamp': memory.timestamp,
                        'importance': memory.importance
                    }
                    embedding_metadata.update(metadata_dict)
                    
                    self.embedding_manager.add_text(
                        text_id=memory_id,
                        text=content,
                        metadata=embedding_metadata
                    )
                
                self.save_memories()
                return True
        return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID"""
        for i, memory in enumerate(self.memories):
            if memory.id == memory_id:
                del self.memories[i]
                self.save_memories()
                return True
        return False
    
    def get_memory_context(self, query: str, max_length: int = 1000) -> str:
        """Get relevant memory context for a query"""
        relevant_memories = self.search_memories(query, max_results=5)
        
        if not relevant_memories:
            return ""
        
        context_parts = []
        current_length = 0
        
        for memory in relevant_memories:
            memory_text = f"[{datetime.fromtimestamp(memory.timestamp).strftime('%Y-%m-%d %H:%M')}] {memory.content}"
            
            if current_length + len(memory_text) > max_length:
                break
            
            context_parts.append(memory_text)
            current_length += len(memory_text)
        
        if context_parts:
            return "Relevant memories:\\n" + "\\n".join(context_parts)
        return ""
    
    def _cleanup_old_memories(self) -> None:
        """Remove old memories if we exceed the maximum limit"""
        if len(self.memories) <= self.config.max_memory_entries:
            return
        
        # Sort by importance and timestamp, keep the most important and recent
        self.memories.sort(key=lambda m: (m.importance, m.timestamp), reverse=True)
        self.memories = self.memories[:self.config.max_memory_entries]
    
    def load_memories(self) -> None:
        """Load memories from file"""
        if not os.path.exists(self.memory_file):
            self.memories = []
            return
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.memories = [MemoryEntry.from_dict(entry) for entry in data]
        except Exception as e:
            logging.error(f"Failed to load memories: {e}")
            self.memories = []
    
    def save_memories(self) -> None:
        """Save memories to file"""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                data = [memory.to_dict() for memory in self.memories]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save memories: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        if not self.memories:
            return {
                'total_memories': 0,
                'average_importance': 0.0,
                'oldest_memory': None,
                'newest_memory': None
            }
        
        timestamps = [m.timestamp for m in self.memories]
        importances = [m.importance for m in self.memories]
        
        return {
            'total_memories': len(self.memories),
            'average_importance': sum(importances) / len(importances),
            'oldest_memory': datetime.fromtimestamp(min(timestamps)).isoformat(),
            'newest_memory': datetime.fromtimestamp(max(timestamps)).isoformat()
        }
    
    def clear_memories(self) -> None:
        """Clear all memories"""
        self.memories = []
        if self.embedding_manager:
            self.embedding_manager.clear_embeddings()
        self.save_memories()