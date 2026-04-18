"""Keyword-based retriever"""

from typing import List, Dict
from dataclasses import dataclass
from .document_indexer import Document, RetrievalResult


class KeywordRetriever:
    """Keyword-based retrieval using TF-IDF-like scoring"""

    def retrieve(
        self,
        query: str,
        documents: List[Document],
        limit: int = 10
    ) -> List[RetrievalResult]:
        """
        Retrieve documents using keyword matching

        Args:
            query: Search query
            documents: List of documents to search
            limit: Maximum number of results

        Returns:
            List of retrieval results
        """
        if not documents:
            return []

        query_words = set(query.lower().split())
        doc_scores = []

        for doc in documents:
            doc_words = set(doc.content.lower().split())
            
            # Calculate keyword score
            matching_words = query_words.intersection(doc_words)
            score = len(matching_words) / len(query_words) if query_words else 0
            
            # Boost score for exact phrase matches
            if query.lower() in doc.content.lower():
                score += 0.5
            
            if score > 0:
                doc_scores.append(RetrievalResult(
                    document=doc,
                    score=score,
                    metadata={"method": "keyword", "matches": len(matching_words)}
                ))

        # Sort by score and return top results
        doc_scores.sort(key=lambda x: x.score, reverse=True)
        return doc_scores[:limit]
