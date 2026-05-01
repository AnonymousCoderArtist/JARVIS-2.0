"""Document indexer for RAG system"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Document:
    """A document in the index"""
    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    embedding: list[float] | None = None


class DocumentIndexer:
    """Manages document storage, indexing, and retrieval"""

    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.keyword_index: dict[str, list[str]] = {}

    def add_document(
        self,
        content: str,
        metadata: dict | None = None
    ) -> str:
        """
        Add a document to the index

        Args:
            content: Document content
            metadata: Optional metadata

        Returns:
            Document ID
        """
        doc_id = self._generate_id(content)

        document = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {}
        )

        self.documents[doc_id] = document
        self._update_keyword_index(doc_id, content)

        return doc_id

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for a document"""
        return hashlib.md5(content.encode()).hexdigest()

    def _update_keyword_index(self, doc_id: str, content: str):
        """Update the keyword index for a document"""
        # Simple tokenization and indexing
        words = content.lower().split()
        for word in set(words):
            if word not in self.keyword_index:
                self.keyword_index[word] = []
            if doc_id not in self.keyword_index[word]:
                self.keyword_index[word].append(doc_id)

    def update_document(
        self,
        doc_id: str,
        content: str | None = None,
        metadata: dict | None = None
    ) -> bool:
        """
        Update a document

        Args:
            doc_id: Document ID
            content: New content (optional)
            metadata: New metadata (optional)

        Returns:
            True if successful, False otherwise
        """
        if doc_id not in self.documents:
            return False

        document = self.documents[doc_id]

        if content:
            # Remove old keyword entries
            old_content = document.content
            self._remove_from_keyword_index(doc_id, old_content)

            document.content = content
            self._update_keyword_index(doc_id, content)

        if metadata:
            document.metadata.update(metadata)

        document.timestamp = datetime.now()
        return True

    def _remove_from_keyword_index(self, doc_id: str, content: str):
        """Remove document from keyword index"""
        words = content.lower().split()
        for word in set(words):
            if word in self.keyword_index and doc_id in self.keyword_index[word]:
                self.keyword_index[word].remove(doc_id)
                if not self.keyword_index[word]:
                    del self.keyword_index[word]

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the index

        Args:
            doc_id: Document ID

        Returns:
            True if successful, False otherwise
        """
        if doc_id not in self.documents:
            return False

        document = self.documents[doc_id]
        self._remove_from_keyword_index(doc_id, document.content)
        del self.documents[doc_id]

        return True

    def get_document(self, doc_id: str) -> Document | None:
        """
        Get a document by ID

        Args:
            doc_id: Document ID

        Returns:
            Document or None if not found
        """
        return self.documents.get(doc_id)

    def search_documents(
        self,
        query: str,
        limit: int = 10
    ) -> list[Document]:
        """
        Search documents by keyword

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching documents
        """
        query_words = query.lower().split()
        doc_scores = {}

        for word in query_words:
            if word in self.keyword_index:
                for doc_id in self.keyword_index[word]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1

        # Sort by score and return top results
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            self.documents[doc_id]
            for doc_id, _ in sorted_docs[:limit]
        ]

    def get_stats(self) -> dict:
        """Get index statistics"""
        return {
            "total_documents": len(self.documents),
            "total_keywords": len(self.keyword_index),
            "avg_doc_length": sum(len(d.content) for d in self.documents.values()) / len(self.documents) if self.documents else 0
        }

    def clear(self):
        """Clear all documents and index"""
        self.documents.clear()
        self.keyword_index.clear()
