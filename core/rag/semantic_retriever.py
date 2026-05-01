"""Semantic retriever using embeddings"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from .document_indexer import Document


@dataclass
class RetrievalResult:
    """Result from a retrieval operation"""
    document: Document
    score: float
    metadata: dict[str, Any] | None = None


class SemanticRetriever:
    """Embedding-based semantic search"""

    def __init__(self, embedding_backend: str | None = None):
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

    def _get_embedding(self, text: str) -> np.ndarray | None:
        """Get embedding for text"""
        if self._embedding_model:
            return self._embedding_model.encode(text)
        return None

    def retrieve(
        self,
        query: str,
        documents: list[Document],
        limit: int = 10,
        threshold: float = 0.0
    ) -> list[RetrievalResult]:
        """
        Retrieve documents using semantic search

        Args:
            query: Search query
            documents: List of documents to search
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of retrieval results
        """
        if not documents:
            return []

        # If no embedding backend, return empty results
        if not self.embedding_backend:
            return []

        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []

        results = []
        for doc in documents:
            doc_embedding = doc.embedding
            if doc_embedding is not None:
                similarity = self._cosine_similarity(query_embedding, np.array(doc_embedding))
                if similarity >= threshold:
                    results.append(RetrievalResult(
                        document=doc,
                        score=similarity,
                        metadata={"method": "semantic"}
                    ))

        # Sort by score and return top results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        return dot_product / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

    def index_documents(self, documents: list[Document]):
        """
        Add embeddings to documents

        Args:
            documents: List of documents to index
        """
        if not self.embedding_backend:
            return

        for doc in documents:
            if doc.embedding is None:
                embedding = self._get_embedding(doc.content)
                if embedding is not None:
                    doc.embedding = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
