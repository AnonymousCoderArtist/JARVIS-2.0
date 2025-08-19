#!/usr/bin/env python3
"""
Demonstration of embedding functionality in the enhanced JARVIS conversation system
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/JARVIS/JARVIS')

from conversation import JARVISConversation
from conversation.config import ConversationConfig, EmbeddingConfig, EmbeddingBackend

def demo_sentence_transformers():
    """Demo with sentence transformers (if available)"""
    print("🤖 Testing with Sentence Transformers...")
    
    try:
        # Configure for sentence transformers
        config = ConversationConfig()
        config.embedding = EmbeddingConfig(
            backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2"
        )
        
        conversation = JARVISConversation(name="TestUser", config=config)
        
        # Add some sample memories
        memories = [
            "User prefers Python programming language",
            "User works on machine learning projects",
            "User likes to use VS Code editor",
            "User is interested in AI development",
            "User uses Linux operating system"
        ]
        
        for memory_text in memories:
            conversation.memory_manager.add_memory(memory_text, importance=0.7)
        
        print(f"✅ Added {len(memories)} memories with embeddings")
        
        # Test semantic search
        search_queries = [
            "coding preferences",
            "development tools",
            "artificial intelligence"
        ]
        
        for query in search_queries:
            results = conversation.memory_manager.search_memories(query, max_results=3)
            print(f"🔍 Search '{query}': Found {len(results)} relevant memories")
            for memory in results:
                print(f"   - {memory.content[:50]}...")
        
        # Test conversation with embeddings
        prompt = conversation.generate_complete_prompt("What do you know about my programming preferences?")
        print(f"✅ Generated context-aware prompt (length: {len(prompt)})")
        
        return True
        
    except ImportError as e:
        print(f"⚠️ Sentence transformers not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing sentence transformers: {e}")
        return False

def demo_openai_embeddings():
    """Demo with OpenAI embeddings (if API key available)"""
    print("🔑 Testing with OpenAI embeddings...")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ OpenAI API key not available in environment variables")
        return False
    
    try:
        # Configure for OpenAI
        config = ConversationConfig()
        config.embedding = EmbeddingConfig(
            backend=EmbeddingBackend.OPENAI,
            api_key=api_key,
            model_name="text-embedding-ada-002"
        )
        
        conversation = JARVISConversation(name="TestUser", config=config)
        
        # Add a test memory
        conversation.memory_manager.add_memory(
            "User is working on a neural network project using TensorFlow",
            importance=0.8
        )
        
        print("✅ Added memory with OpenAI embeddings")
        
        # Test search
        results = conversation.memory_manager.search_memories("deep learning framework")
        print(f"🔍 Found {len(results)} relevant memories for 'deep learning framework'")
        
        return True
        
    except ImportError as e:
        print(f"⚠️ OpenAI library not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing OpenAI embeddings: {e}")
        return False

def demo_no_embeddings():
    """Demo with embeddings disabled"""
    print("🚫 Testing with embeddings disabled...")
    
    config = ConversationConfig()
    config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
    
    conversation = JARVISConversation(name="TestUser", config=config)
    
    # Add memories
    memories = [
        "User mentioned liking pizza",
        "User is from New York",
        "User works as a software engineer"
    ]
    
    for memory_text in memories:
        conversation.memory_manager.add_memory(memory_text, importance=0.6)
    
    print(f"✅ Added {len(memories)} memories without embeddings")
    
    # Test keyword-based search
    results = conversation.memory_manager.search_memories("software engineer")
    print(f"🔍 Keyword search 'software engineer': Found {len(results)} memories")
    
    # Show stats
    stats = conversation.get_conversation_summary()
    print(f"📊 System stats: {stats['embedding_stats']}")
    
    return True

def main():
    """Run embedding demonstrations"""
    print("🚀 JARVIS Enhanced Conversation System - Embedding Demonstrations\n")
    
    demos = [
        ("No Embeddings", demo_no_embeddings),
        ("Sentence Transformers", demo_sentence_transformers),
        ("OpenAI Embeddings", demo_openai_embeddings)
    ]
    
    results = []
    
    for name, demo_func in demos:
        print(f"\n{'='*50}")
        print(f"Testing: {name}")
        print('='*50)
        
        try:
            result = demo_func()
            results.append((name, result))
            if result:
                print(f"✅ {name} demo completed successfully\n")
            else:
                print(f"⚠️ {name} demo completed with limitations\n")
        except Exception as e:
            print(f"❌ {name} demo failed: {e}\n")
            results.append((name, False))
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    for name, success in results:
        status = "✅ PASSED" if success else "⚠️ LIMITED/FAILED"
        print(f"{name}: {status}")
    
    print(f"\nEmbedding backends available:")
    print("• None (keyword search): Always available")
    
    try:
        import sentence_transformers
        print("• Sentence Transformers: ✅ Available")
    except ImportError:
        print("• Sentence Transformers: ❌ Not installed (pip install sentence-transformers)")
    
    try:
        import openai
        api_key_status = "✅ Set" if os.getenv("OPENAI_API_KEY") else "❌ Not set"
        print(f"• OpenAI Embeddings: ✅ Library available, API key: {api_key_status}")
    except ImportError:
        print("• OpenAI Embeddings: ❌ Not installed (pip install openai)")

if __name__ == "__main__":
    main()