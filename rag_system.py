"""
JARVIS RAG (Retrieval Augmented Generation) System

A comprehensive RAG implementation with multiple retrieval strategies,
advanced indexing, and intelligent generation capabilities.
"""

import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

# Optional imports with fallbacks
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from conversation.embeddings import EmbeddingManager, EmbeddingBackend
from conversation.config import EmbeddingConfig


@dataclass
class Document:
    """Represents a document in the RAG system."""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class RetrievalResult:
    """Represents a retrieved document with similarity score."""
    document: Document
    score: float
    rank: int
    retrieval_method: str


@dataclass
class RAGConfig:
    """Configuration for the RAG system."""
    storage_path: str = "History/rag_storage"
    max_documents: int = 10000
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_backend: str = "sentence_transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.7
    max_retrieval_results: int = 10
    rerank_results: bool = True
    enable_keyword_search: bool = True
    enable_semantic_search: bool = True
    index_refresh_interval: int = 3600  # seconds


class DocumentIndexer:
    """Handles document indexing and storage."""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.storage_path = Path(config.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.documents_file = self.storage_path / "documents.json"
        self.index_file = self.storage_path / "index.json"
        self.embeddings_file = self.storage_path / "embeddings.npy"
        
        self.documents: Dict[str, Document] = {}
        self.keyword_index: Dict[str, List[str]] = {}
        # Initialize embedding manager with appropriate config
        embedding_config = EmbeddingConfig(backend=EmbeddingBackend.NONE)
        self.embedding_manager = EmbeddingManager(embedding_config, str(self.storage_path))
        
        self._load_documents()
        self._build_keyword_index()
        
        logging.info(f"DocumentIndexer initialized with {len(self.documents)} documents")
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Add a document to the index."""
        if metadata is None:
            metadata = {}
        
        # Generate document ID
        doc_id = self._generate_doc_id(content)
        
        # Check if document already exists
        if doc_id in self.documents:
            return doc_id
        
        # Create document
        document = Document(
            id=doc_id,
            content=content,
            metadata=metadata
        )
        
        # Generate embedding if available
        if self.embedding_manager:
            try:
                embedding = self.embedding_manager.generate_embedding(content)
                document.embedding = embedding
            except Exception as e:
                logging.warning(f"Failed to generate embedding for document {doc_id}: {e}")
        
        # Add to documents
        self.documents[doc_id] = document
        
        # Update keyword index
        self._add_to_keyword_index(doc_id, content)
        
        # Save changes
        self._save_documents()
        
        logging.info(f"Added document {doc_id} to index")
        return doc_id
    
    def update_document(self, doc_id: str, content: str = None, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing document."""
        if doc_id not in self.documents:
            return False
        
        document = self.documents[doc_id]
        
        if content is not None:
            # Remove from old keyword index
            self._remove_from_keyword_index(doc_id, document.content)
            
            # Update content
            document.content = content
            document.updated_at = datetime.now()
            
            # Regenerate embedding
            if self.embedding_manager:
                try:
                    embedding = self.embedding_manager.generate_embedding(content)
                    document.embedding = embedding
                except Exception as e:
                    logging.warning(f"Failed to update embedding for document {doc_id}: {e}")
            
            # Update keyword index
            self._add_to_keyword_index(doc_id, content)
        
        if metadata is not None:
            document.metadata.update(metadata)
            document.updated_at = datetime.now()
        
        self._save_documents()
        logging.info(f"Updated document {doc_id}")
        return True
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if doc_id not in self.documents:
            return False
        
        document = self.documents[doc_id]
        
        # Remove from keyword index
        self._remove_from_keyword_index(doc_id, document.content)
        
        # Remove from documents
        del self.documents[doc_id]
        
        self._save_documents()
        logging.info(f"Removed document {doc_id}")
        return True
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self.documents.get(doc_id)
    
    def search_documents(self, query: str, limit: int = None) -> List[str]:
        """Search documents using keyword matching."""
        if limit is None:
            limit = self.config.max_retrieval_results
        
        query_terms = self._tokenize(query.lower())
        doc_scores = {}
        
        for term in query_terms:
            if term in self.keyword_index:
                for doc_id in self.keyword_index[term]:
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = 0
                    doc_scores[doc_id] += 1
        
        # Sort by score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in sorted_docs[:limit]]
    
    def get_all_documents(self) -> List[Document]:
        """Get all documents."""
        return list(self.documents.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get indexer statistics."""
        total_docs = len(self.documents)
        docs_with_embeddings = sum(1 for doc in self.documents.values() if doc.embedding)
        
        return {
            "total_documents": total_docs,
            "documents_with_embeddings": docs_with_embeddings,
            "keyword_index_size": len(self.keyword_index),
            "storage_path": str(self.storage_path),
            "last_update": max(doc.updated_at for doc in self.documents.values()) if self.documents else None
        }
    
    def _generate_doc_id(self, content: str) -> str:
        """Generate a unique document ID."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        timestamp = int(datetime.now().timestamp())
        return f"doc_{timestamp}_{content_hash[:8]}"
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        import re
        return [word.strip() for word in re.findall(r'\b\w+\b', text.lower()) if len(word.strip()) > 2]
    
    def _add_to_keyword_index(self, doc_id: str, content: str):
        """Add document to keyword index."""
        tokens = self._tokenize(content)
        for token in tokens:
            if token not in self.keyword_index:
                self.keyword_index[token] = []
            if doc_id not in self.keyword_index[token]:
                self.keyword_index[token].append(doc_id)
    
    def _remove_from_keyword_index(self, doc_id: str, content: str):
        """Remove document from keyword index."""
        tokens = self._tokenize(content)
        for token in tokens:
            if token in self.keyword_index and doc_id in self.keyword_index[token]:
                self.keyword_index[token].remove(doc_id)
                if not self.keyword_index[token]:
                    del self.keyword_index[token]
    
    def _build_keyword_index(self):
        """Build keyword index from existing documents."""
        self.keyword_index = {}
        for doc_id, document in self.documents.items():
            self._add_to_keyword_index(doc_id, document.content)
    
    def _load_documents(self):
        """Load documents from storage."""
        if self.documents_file.exists():
            try:
                with open(self.documents_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.documents = {}
                for doc_data in data:
                    doc = Document(
                        id=doc_data['id'],
                        content=doc_data['content'],
                        metadata=doc_data['metadata'],
                        embedding=doc_data.get('embedding'),
                        created_at=datetime.fromisoformat(doc_data['created_at']),
                        updated_at=datetime.fromisoformat(doc_data['updated_at'])
                    )
                    self.documents[doc.id] = doc
                    
                logging.info(f"Loaded {len(self.documents)} documents from storage")
            except Exception as e:
                logging.error(f"Failed to load documents: {e}")
                self.documents = {}
    
    def _save_documents(self):
        """Save documents to storage."""
        try:
            data = []
            for document in self.documents.values():
                doc_data = {
                    'id': document.id,
                    'content': document.content,
                    'metadata': document.metadata,
                    'embedding': document.embedding,
                    'created_at': document.created_at.isoformat(),
                    'updated_at': document.updated_at.isoformat()
                }
                data.append(doc_data)
            
            with open(self.documents_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logging.debug(f"Saved {len(data)} documents to storage")
        except Exception as e:
            logging.error(f"Failed to save documents: {e}")


class SemanticRetriever:
    """Handles semantic retrieval using embeddings."""
    
    def __init__(self, indexer: DocumentIndexer, config: RAGConfig):
        self.indexer = indexer
        self.config = config
        self.embedding_manager = indexer.embedding_manager
    
    def retrieve(self, query: str, limit: int = None) -> List[RetrievalResult]:
        """Retrieve semantically similar documents."""
        if limit is None:
            limit = self.config.max_retrieval_results
        
        if not self.embedding_manager:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_manager.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Calculate similarities
            results = []
            for doc_id, document in self.indexer.documents.items():
                if document.embedding:
                    similarity = self._calculate_similarity(query_embedding, document.embedding)
                    if similarity >= self.config.similarity_threshold:
                        results.append(RetrievalResult(
                            document=document,
                            score=similarity,
                            rank=0,  # Will be set after sorting
                            retrieval_method="semantic"
                        ))
            
            # Sort by similarity score
            results.sort(key=lambda x: x.score, reverse=True)
            
            # Set ranks and limit results
            for i, result in enumerate(results[:limit]):
                result.rank = i + 1
            
            return results[:limit]
            
        except Exception as e:
            logging.error(f"Semantic retrieval failed: {e}")
            return []
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        try:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                import numpy as np
                vec1 = np.array(embedding1)
                vec2 = np.array(embedding2)
                
                # Cosine similarity
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                
                return dot_product / (norm1 * norm2)
            else:
                # Fallback to simple dot product
                return sum(a * b for a, b in zip(embedding1, embedding2))
        except Exception as e:
            logging.error(f"Similarity calculation failed: {e}")
            return 0.0


class KeywordRetriever:
    """Handles keyword-based retrieval."""
    
    def __init__(self, indexer: DocumentIndexer, config: RAGConfig):
        self.indexer = indexer
        self.config = config
    
    def retrieve(self, query: str, limit: int = None) -> List[RetrievalResult]:
        """Retrieve documents using keyword matching."""
        if limit is None:
            limit = self.config.max_retrieval_results
        
        doc_ids = self.indexer.search_documents(query, limit)
        
        results = []
        for i, doc_id in enumerate(doc_ids):
            document = self.indexer.get_document(doc_id)
            if document:
                # Simple scoring based on term frequency
                score = self._calculate_keyword_score(query, document.content)
                results.append(RetrievalResult(
                    document=document,
                    score=score,
                    rank=i + 1,
                    retrieval_method="keyword"
                ))
        
        return results
    
    def _calculate_keyword_score(self, query: str, content: str) -> float:
        """Calculate keyword relevance score."""
        query_terms = set(self.indexer._tokenize(query.lower()))
        content_terms = self.indexer._tokenize(content.lower())
        
        if not query_terms:
            return 0.0
        
        # Count term occurrences
        matches = sum(1 for term in content_terms if term in query_terms)
        
        # Normalize by content length
        score = matches / len(content_terms) if content_terms else 0.0
        
        return min(score * 10, 1.0)  # Scale and cap at 1.0


class HybridRetriever:
    """Combines semantic and keyword retrieval."""
    
    def __init__(self, indexer: DocumentIndexer, config: RAGConfig):
        self.indexer = indexer
        self.config = config
        self.semantic_retriever = SemanticRetriever(indexer, config)
        self.keyword_retriever = KeywordRetriever(indexer, config)
    
    def retrieve(self, query: str, limit: int = None) -> List[RetrievalResult]:
        """Retrieve using hybrid approach."""
        if limit is None:
            limit = self.config.max_retrieval_results
        
        results = []
        
        # Get semantic results
        if self.config.enable_semantic_search:
            semantic_results = self.semantic_retriever.retrieve(query, limit)
            results.extend(semantic_results)
        
        # Get keyword results
        if self.config.enable_keyword_search:
            keyword_results = self.keyword_retriever.retrieve(query, limit)
            
            # Merge results, avoiding duplicates
            existing_doc_ids = {r.document.id for r in results}
            for result in keyword_results:
                if result.document.id not in existing_doc_ids:
                    results.append(result)
        
        # Re-rank if enabled
        if self.config.rerank_results and len(results) > 1:
            results = self._rerank_results(query, results)
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Update ranks
        for i, result in enumerate(results[:limit]):
            result.rank = i + 1
        
        return results[:limit]
    
    def _rerank_results(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Re-rank results using hybrid scoring."""
        # Simple re-ranking: combine semantic and keyword scores
        for result in results:
            semantic_score = result.score if result.retrieval_method == "semantic" else 0.0
            keyword_score = result.score if result.retrieval_method == "keyword" else 0.0
            
            # If we only have one type of score, try to get the other
            if semantic_score == 0.0 and self.config.enable_semantic_search:
                try:
                    query_embedding = self.semantic_retriever.embedding_manager.generate_embedding(query)
                    if query_embedding and result.document.embedding:
                        semantic_score = self.semantic_retriever._calculate_similarity(
                            query_embedding, result.document.embedding
                        )
                except:
                    pass
            
            if keyword_score == 0.0 and self.config.enable_keyword_search:
                keyword_score = self.keyword_retriever._calculate_keyword_score(
                    query, result.document.content
                )
            
            # Combine scores (weighted average)
            result.score = 0.7 * semantic_score + 0.3 * keyword_score
        
        return results


class RAGSystem:
    """Complete RAG (Retrieval Augmented Generation) system."""
    
    def __init__(self, config: RAGConfig = None):
        self.config = config or RAGConfig()
        self.indexer = DocumentIndexer(self.config)
        self.retriever = HybridRetriever(self.indexer, self.config)
        
        logging.info("RAG System initialized")
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Add a document to the RAG system."""
        return self.indexer.add_document(content, metadata)
    
    def add_conversation_memory(self, user_message: str, ai_response: str, 
                              metadata: Dict[str, Any] = None) -> str:
        """Add a conversation exchange as a document."""
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "type": "conversation",
            "user_message": user_message,
            "ai_response": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Combine user message and AI response for content
        content = f"User: {user_message}\nAssistant: {ai_response}"
        
        return self.add_document(content, metadata)
    
    def retrieve_context(self, query: str, limit: int = None) -> List[RetrievalResult]:
        """Retrieve relevant context for a query."""
        return self.retriever.retrieve(query, limit)
    
    def generate_context_prompt(self, query: str, max_context_length: int = 2000) -> str:
        """Generate a context-enhanced prompt for the query."""
        results = self.retrieve_context(query)
        
        if not results:
            return query
        
        # Build context from retrieved documents
        context_parts = []
        current_length = 0
        
        for result in results:
            content = result.document.content
            
            # Add source information
            source_info = f"[Source: {result.retrieval_method}, Score: {result.score:.3f}]"
            context_part = f"{source_info}\n{content}\n"
            
            # Check length limit
            if current_length + len(context_part) > max_context_length:
                # Try to fit a truncated version
                remaining_space = max_context_length - current_length - len(source_info) - 10
                if remaining_space > 100:  # Only if we have reasonable space
                    truncated_content = content[:remaining_space] + "..."
                    context_part = f"{source_info}\n{truncated_content}\n"
                    context_parts.append(context_part)
                break
            
            context_parts.append(context_part)
            current_length += len(context_part)
        
        if context_parts:
            context = "\n".join(context_parts)
            enhanced_prompt = f"""Based on the following relevant context, please answer the query:

CONTEXT:
{context}

QUERY: {query}

Please provide a comprehensive answer using the context above when relevant."""
            return enhanced_prompt
        
        return query
    
    def search_memories(self, query: str, memory_type: str = None) -> List[RetrievalResult]:
        """Search for specific memories."""
        results = self.retrieve_context(query)
        
        # Filter by memory type if specified
        if memory_type:
            results = [r for r in results if r.document.metadata.get("type") == memory_type]
        
        return results
    
    def get_conversation_history(self, limit: int = 10) -> List[Document]:
        """Get recent conversation history."""
        conversation_docs = []
        
        for document in self.indexer.get_all_documents():
            if document.metadata.get("type") == "conversation":
                conversation_docs.append(document)
        
        # Sort by creation time (most recent first)
        conversation_docs.sort(key=lambda x: x.created_at, reverse=True)
        
        return conversation_docs[:limit]
    
    def cleanup_old_documents(self, days_old: int = 30):
        """Remove documents older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        
        for doc_id, document in list(self.indexer.documents.items()):
            if document.created_at < cutoff_date:
                self.indexer.remove_document(doc_id)
                removed_count += 1
        
        logging.info(f"Cleaned up {removed_count} old documents")
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics."""
        indexer_stats = self.indexer.get_stats()
        
        conversation_count = sum(
            1 for doc in self.indexer.documents.values()
            if doc.metadata.get("type") == "conversation"
        )
        
        return {
            **indexer_stats,
            "conversation_documents": conversation_count,
            "semantic_search_enabled": self.config.enable_semantic_search,
            "keyword_search_enabled": self.config.enable_keyword_search,
            "embedding_backend": self.config.embedding_backend
        }
    
    def export_data(self, format_type: str = "json") -> str:
        """Export RAG data."""
        if format_type == "json":
            data = {
                "config": asdict(self.config),
                "documents": [asdict(doc) for doc in self.indexer.get_all_documents()],
                "stats": self.get_stats(),
                "export_timestamp": datetime.now().isoformat()
            }
            return json.dumps(data, indent=2, default=str)
        
        elif format_type == "txt":
            lines = ["JARVIS RAG System Export", "=" * 50, ""]
            
            # Add stats
            stats = self.get_stats()
            lines.append("STATISTICS:")
            for key, value in stats.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
            
            # Add documents
            lines.append("DOCUMENTS:")
            for doc in self.indexer.get_all_documents():
                lines.append(f"ID: {doc.id}")
                lines.append(f"Created: {doc.created_at}")
                lines.append(f"Metadata: {doc.metadata}")
                lines.append(f"Content: {doc.content[:200]}...")
                lines.append("-" * 40)
            
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format_type}")


# Integration with existing conversation system
def enhance_conversation_with_rag(conversation_instance, rag_config: RAGConfig = None):
    """Enhance an existing conversation instance with RAG capabilities."""
    if not hasattr(conversation_instance, 'rag_system'):
        conversation_instance.rag_system = RAGSystem(rag_config)
    
    # Store original method
    original_add_message = conversation_instance.add_message
    
    def enhanced_add_message(speaker: str, message: str, importance: float = 0.5):
        """Enhanced add_message that feeds into RAG system."""
        # Call original method
        result = original_add_message(speaker, message, importance)
        
        # Add to RAG if this is a significant exchange
        if importance >= 0.6:  # Only store important messages
            metadata = {
                "speaker": speaker,
                "importance": importance,
                "timestamp": datetime.now().isoformat()
            }
            conversation_instance.rag_system.add_document(message, metadata)
        
        return result
    
    # Replace method
    conversation_instance.add_message = enhanced_add_message
    
    # Add RAG-enhanced prompt generation
    def generate_rag_enhanced_prompt(self, user_input: str) -> str:
        """Generate a prompt enhanced with RAG context."""
        if hasattr(self, 'rag_system'):
            return self.rag_system.generate_context_prompt(user_input)
        else:
            return user_input
    
    # Add method to conversation instance
    conversation_instance.generate_rag_enhanced_prompt = generate_rag_enhanced_prompt.__get__(
        conversation_instance, conversation_instance.__class__
    )
    
    return conversation_instance


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize RAG system
    config = RAGConfig(
        embedding_backend="sentence_transformers" if SENTENCE_TRANSFORMERS_AVAILABLE else "none"
    )
    rag = RAGSystem(config)
    
    # Add some sample documents
    rag.add_document("Python is a high-level programming language.", {"topic": "programming"})
    rag.add_document("Machine learning involves training algorithms on data.", {"topic": "AI"})
    rag.add_conversation_memory(
        "What is Python?",
        "Python is a versatile programming language known for its simplicity."
    )
    
    # Test retrieval
    results = rag.retrieve_context("programming languages")
    print(f"Found {len(results)} relevant documents")
    
    # Test enhanced prompt generation
    enhanced_prompt = rag.generate_context_prompt("Tell me about Python")
    print("Enhanced prompt:", enhanced_prompt[:200] + "...")
    
    # Show stats
    stats = rag.get_stats()
    print("RAG Stats:", stats)