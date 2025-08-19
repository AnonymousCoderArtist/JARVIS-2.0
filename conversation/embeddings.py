"""
Embedding management system with support for multiple backends
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

from .config import EmbeddingConfig, EmbeddingBackend


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        pass
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        import math
        
        # Dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(a * a for a in embedding2))
        
        # Cosine similarity
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""
    
    def __init__(self, api_key: str, model_name: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None
    
    def _get_client(self):
        """Lazy loading of OpenAI client"""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("OpenAI library not installed. Install with: pip install openai")
        return self._client
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model_name,
            input=text
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model_name,
            input=texts
        )
        return [data.embedding for data in response.data]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    def _get_model(self):
        """Lazy loading of sentence transformer model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("Sentence Transformers library not installed. Install with: pip install sentence-transformers")
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        model = self._get_model()
        embedding = model.encode(text)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        model = self._get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()


class NoEmbeddingProvider(EmbeddingProvider):
    """Dummy provider when embeddings are disabled"""
    
    def embed_text(self, text: str) -> List[float]:
        """Return empty embedding"""
        return []
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Return empty embeddings"""
        return [[] for _ in texts]


class EmbeddingManager:
    """Manages embeddings for conversation history and memory"""
    
    def __init__(self, config: EmbeddingConfig, storage_path: str):
        self.config = config
        self.storage_path = storage_path
        self.provider = self._create_provider()
        self.embeddings_db: Dict[str, Dict[str, Any]] = {}
        self.load_embeddings()
    
    def _create_provider(self) -> EmbeddingProvider:
        """Create appropriate embedding provider based on config"""
        if self.config.backend == EmbeddingBackend.OPENAI:
            if not self.config.api_key:
                raise ValueError("OpenAI API key required for OpenAI embedding backend")
            return OpenAIEmbeddingProvider(self.config.api_key, self.config.model_name)
        elif self.config.backend == EmbeddingBackend.SENTENCE_TRANSFORMERS:
            return SentenceTransformerEmbeddingProvider(self.config.model_name)
        else:
            return NoEmbeddingProvider()
    
    def add_text(self, text_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add text with its embedding to the database"""
        if self.config.backend == EmbeddingBackend.NONE:
            return
        
        try:
            embedding = self.provider.embed_text(text)
            self.embeddings_db[text_id] = {
                'text': text,
                'embedding': embedding,
                'metadata': metadata or {}
            }
            self.save_embeddings()
        except Exception as e:
            logging.error(f"Failed to generate embedding for text_id {text_id}: {e}")
    
    def search_similar(self, query: str, top_k: Optional[int] = None) -> List[Tuple[str, float, str]]:
        """Search for similar texts based on embedding similarity"""
        if self.config.backend == EmbeddingBackend.NONE or not self.embeddings_db:
            return []
        
        top_k = top_k or self.config.max_results
        
        try:
            query_embedding = self.provider.embed_text(query)
            similarities = []
            
            for text_id, data in self.embeddings_db.items():
                if not data['embedding']:  # Skip empty embeddings
                    continue
                
                similarity = self.provider.calculate_similarity(
                    query_embedding, data['embedding']
                )
                
                if similarity >= self.config.similarity_threshold:
                    similarities.append((text_id, similarity, data['text']))
            
            # Sort by similarity (descending) and return top_k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]
        
        except Exception as e:
            logging.error(f"Failed to search similar texts: {e}")
            return []
    
    def load_embeddings(self) -> None:
        """Load embeddings from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.embeddings_db = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load embeddings: {e}")
                self.embeddings_db = {}
        else:
            self.embeddings_db = {}
    
    def save_embeddings(self) -> None:
        """Save embeddings to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.embeddings_db, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save embeddings: {e}")
    
    def clear_embeddings(self) -> None:
        """Clear all stored embeddings"""
        self.embeddings_db = {}
        self.save_embeddings()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        return {
            'total_embeddings': len(self.embeddings_db),
            'backend': self.config.backend.value,
            'model_name': self.config.model_name,
            'similarity_threshold': self.config.similarity_threshold
        }