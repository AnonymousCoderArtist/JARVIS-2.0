#!/usr/bin/env python3
"""
Test script for the enhanced JARVIS conversation system
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/JARVIS/JARVIS')

from conversation import JARVISConversation
from conversation.config import ConversationConfig, EmbeddingConfig, EmbeddingBackend

def test_basic_conversation():
    """Test basic conversation functionality"""
    print("🔧 Testing basic conversation functionality...")
    
    config = ConversationConfig()
    config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)  # Disable embeddings for basic test
    
    conversation = JARVISConversation(name="TestUser", config=config)
    
    # Test message addition
    msg_id = conversation.add_message("User", "Hello JARVIS")
    print(f"✅ Added message with ID: {msg_id}")
    
    # Test prompt generation
    prompt = conversation.generate_complete_prompt("How are you today?")
    print(f"✅ Generated prompt (length: {len(prompt)})")
    
    # Test conversation summary
    summary = conversation.get_conversation_summary()
    print(f"✅ Conversation summary: {summary}")
    
    return True

def test_memory_system():
    """Test memory management"""
    print("🧠 Testing memory system...")
    
    config = ConversationConfig()
    config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
    
    conversation = JARVISConversation(name="TestUser", config=config)
    
    # Add some test memories
    memory_id = conversation.memory_manager.add_memory(
        content="User prefers Python for programming tasks",
        metadata={"type": "preference"},
        importance=0.8
    )
    print(f"✅ Added memory with ID: {memory_id}")
    
    # Search memories
    results = conversation.memory_manager.search_memories("programming")
    print(f"✅ Found {len(results)} memories for 'programming'")
    
    # Get memory stats
    stats = conversation.memory_manager.get_stats()
    print(f"✅ Memory stats: {stats}")
    
    return True

def test_tool_interaction():
    """Test tool interaction processing"""
    print("🔨 Testing tool interaction processing...")
    
    config = ConversationConfig()
    config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
    
    conversation = JARVISConversation(name="TestUser", config=config)
    
    # Simulate a tool interaction
    user_input = "Search for Python tutorials"
    ai_response = "I found several excellent Python tutorials for you."
    tool_outputs = [
        {
            "name": "websearch",
            "output": "Found 10 Python tutorial websites",
            "arguments": {"query": "Python tutorials"}
        }
    ]
    
    conversation.process_interaction(user_input, ai_response, tool_outputs)
    print("✅ Processed tool interaction successfully")
    
    # Check if memory was created
    stats = conversation.memory_manager.get_stats()
    print(f"✅ Memory stats after interaction: {stats}")
    
    return True

def test_conversation_export():
    """Test conversation export functionality"""
    print("📤 Testing conversation export...")
    
    config = ConversationConfig()
    config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
    
    conversation = JARVISConversation(name="TestUser", config=config)
    
    # Add some conversation data
    conversation.add_message("User", "Test message")
    conversation.add_message("JARVIS", "Test response")
    
    # Export as JSON
    json_export = conversation.export_conversation("json")
    print(f"✅ JSON export length: {len(json_export)}")
    
    # Export as text
    txt_export = conversation.export_conversation("txt")
    print(f"✅ Text export length: {len(txt_export)}")
    
    return True

def main():
    """Run all tests"""
    print("🚀 Starting JARVIS Enhanced Conversation System Tests\n")
    
    tests = [
        test_basic_conversation,
        test_memory_system,
        test_tool_interaction,
        test_conversation_export
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
                print("✅ PASSED\n")
            else:
                print("❌ FAILED\n")
        except Exception as e:
            print(f"❌ FAILED with error: {e}\n")
    
    print(f"🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The enhanced conversation system is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit(main())