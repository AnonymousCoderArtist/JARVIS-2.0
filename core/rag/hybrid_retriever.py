"""Hybrid retriever combining semantic and keyword search"""


from .document_indexer import Document
from .keyword_retriever import KeywordRetriever
from .semantic_retriever import RetrievalResult, SemanticRetriever


class HybridRetriever:
    """Combines semantic and keyword retrieval with re-ranking"""

    def __init__(self, embedding_backend: str | None = None):
        self.semantic_retriever = SemanticRetriever(embedding_backend)
        self.keyword_retriever = KeywordRetriever()

    async def retrieve(
        self,
        query: str,
        documents: list[Document],
        limit: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ) -> list[RetrievalResult]:
        """
        Retrieve documents using hybrid search

        Args:
            query: Search query
            documents: List of documents to search
            limit: Maximum number of results
            semantic_weight: Weight for semantic search (0.0 to 1.0)
            keyword_weight: Weight for keyword search (0.0 to 1.0)

        Returns:
            List of retrieval results
        """
        if not documents:
            return []

        # Get results from both retrievers
        semantic_results = self.semantic_retriever.retrieve(
            query, documents, limit * 2
        )
        keyword_results = self.keyword_retriever.retrieve(
            query, documents, limit * 2
        )

        # Combine and re-rank results
        combined_scores = {}

        # Process semantic results
        for result in semantic_results:
            doc_id = result.document.id
            combined_scores[doc_id] = {
                "document": result.document,
                "semantic_score": result.score,
                "keyword_score": 0.0,
                "metadata": result.metadata or {}
            }

        # Process keyword results
        for result in keyword_results:
            doc_id = result.document.id
            if doc_id in combined_scores:
                combined_scores[doc_id]["keyword_score"] = result.score
            else:
                combined_scores[doc_id] = {
                    "document": result.document,
                    "semantic_score": 0.0,
                    "keyword_score": result.score,
                    "metadata": result.metadata or {}
                }

        # Calculate combined scores
        final_results = []
        for _doc_id, data in combined_scores.items():
            combined_score = (
                data["semantic_score"] * semantic_weight +
                data["keyword_score"] * keyword_weight
            )

            final_results.append(RetrievalResult(
                document=data["document"],
                score=combined_score,
                metadata={
                    "method": "hybrid",
                    "semantic_score": data["semantic_score"],
                    "keyword_score": data["keyword_score"]
                }
            ))

        # Sort by combined score and return top results
        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results[:limit]

    def index_documents(self, documents: list):
        """Index documents with embeddings"""
        self.semantic_retriever.index_documents(documents)
