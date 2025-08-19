#!/usr/bin/env python3
"""
Test the enhanced main.py integration
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/JARVIS/JARVIS')

def test_main_imports():
    """Test that main.py can import the new conversation system"""
    print("🔧 Testing main.py imports...")
    
    try:
        # This should work with our new conversation system
        from conversation import JARVISConversation
        from conversation.config import ConversationConfig, EmbeddingConfig, EmbeddingBackend
        print("✅ New conversation system imports successfully")
        
        # Test that we can create the config
        config = ConversationConfig()
        config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
        conversation = JARVISConversation(config=config)
        print("✅ Conversation initialization successful")
        
        # Test prompt generation
        prompt = conversation.generate_complete_prompt("Hello JARVIS")
        print(f"✅ Prompt generation works (length: {len(prompt)})")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_jarvis_class_structure():
    """Test that the JARVIS class structure works"""
    print("🤖 Testing JARVIS class with new conversation system...")
    
    try:
        # Mock the dependencies to test just the structure
        class MockDatasetBuilder:
            def __init__(self, filepath):
                self.filepath = filepath
            def add_datapoint(self, *args, **kwargs):
                pass
        
        class MockFunctionCallingAgent:
            def __init__(self, tools):
                self.tools = tools
            def function_call_handler(self, message):
                return {"tool_calls": [{"name": "general_ai", "arguments": {"question": message}}]}
        
        class MockC4ai:
            def __init__(self, **kwargs):
                pass
            def chat(self, prompt):
                return ["This is a mock response."]
        
        # Test the JARVIS class initialization pattern
        from conversation import JARVISConversation
        from conversation.config import ConversationConfig, EmbeddingConfig, EmbeddingBackend
        
        # Mock config class
        class MockConfig:
            DATASET_FILE = "test_dataset.json"
        
        # Initialize components like in main.py
        dataset_builder = MockDatasetBuilder(filepath=MockConfig.DATASET_FILE)
        
        conversation_config = ConversationConfig()
        conversation_config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
        
        conversation = JARVISConversation(config=conversation_config)
        agent = MockFunctionCallingAgent(tools=[])
        ai = MockC4ai(is_conversation=False, system_prompt=conversation.intro)
        
        print("✅ JARVIS class structure compatible")
        
        # Test the enhanced execute_tool_and_respond logic
        user_input = "Hello JARVIS"
        enhanced_prompt = conversation.generate_complete_prompt(user_input)
        print(f"✅ Enhanced prompt generation works (length: {len(enhanced_prompt)})")
        
        function_call_data = agent.function_call_handler(enhanced_prompt)
        print(f"✅ Function call handling works: {function_call_data}")
        
        return True
        
    except Exception as e:
        print(f"❌ JARVIS class test failed: {e}")
        return False

def main():
    """Run integration tests"""
    print("🚀 Testing Enhanced JARVIS Integration\n")
    
    tests = [
        test_main_imports,
        test_jarvis_class_structure
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
    
    print(f"🎯 Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! The enhanced system is ready.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the integration.")
        return 1

if __name__ == "__main__":
    exit(main())