"""
Test suite for Enhanced JARVIS System
Tests RAG, Agent Coordination, and integrated functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch
import logging

# Import enhanced system components
from rag_system import RAGSystem, RAGConfig, Document
from AGENTS.coordinator import EnhancedJARVIS, TaskPriority, AgentCoordinator
from conversation import JARVISConversation
from conversation.config import ConversationConfig

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)


class TestRAGSystem(unittest.TestCase):
    """Test RAG (Retrieval Augmented Generation) system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = RAGConfig(
            storage_path=os.path.join(self.temp_dir, "rag_test"),
            embedding_backend="none",  # Use keyword search for testing
            enable_semantic_search=False,
            enable_keyword_search=True
        )
        self.rag = RAGSystem(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_document_addition(self):
        """Test adding documents to RAG system."""
        doc_id = self.rag.add_document(
            "Python is a programming language",
            {"topic": "programming"}
        )
        
        self.assertIsNotNone(doc_id)
        self.assertIn(doc_id, self.rag.indexer.documents)
        
        # Check document content
        doc = self.rag.indexer.get_document(doc_id)
        self.assertEqual(doc.content, "Python is a programming language")
        self.assertEqual(doc.metadata["topic"], "programming")
    
    def test_conversation_memory(self):
        """Test adding conversation memories."""
        doc_id = self.rag.add_conversation_memory(
            "What is Python?",
            "Python is a high-level programming language."
        )
        
        self.assertIsNotNone(doc_id)
        doc = self.rag.indexer.get_document(doc_id)
        self.assertEqual(doc.metadata["type"], "conversation")
        self.assertIn("Python", doc.content)
    
    def test_keyword_retrieval(self):
        """Test keyword-based retrieval."""
        # Add test documents
        self.rag.add_document("Python programming tutorial", {"type": "tutorial"})
        self.rag.add_document("Java development guide", {"type": "guide"})
        self.rag.add_document("Machine learning with Python", {"type": "ml"})
        
        # Test retrieval
        results = self.rag.retrieve_context("Python programming")
        
        self.assertGreater(len(results), 0)
        # Should find Python-related documents
        python_docs = [r for r in results if "python" in r.document.content.lower()]
        self.assertGreater(len(python_docs), 0)
    
    def test_context_prompt_generation(self):
        """Test context-enhanced prompt generation."""
        # Add relevant document
        self.rag.add_document(
            "Python is excellent for data science and machine learning",
            {"topic": "programming"}
        )
        
        # Generate enhanced prompt
        enhanced_prompt = self.rag.generate_context_prompt("Tell me about Python")
        
        self.assertIn("Python", enhanced_prompt)
        self.assertIn("CONTEXT:", enhanced_prompt)
        self.assertIn("QUERY:", enhanced_prompt)
    
    def test_stats_and_export(self):
        """Test statistics and data export."""
        # Add some documents
        self.rag.add_document("Test document 1", {"type": "test"})
        self.rag.add_conversation_memory("Hello", "Hi there!")
        
        # Test stats
        stats = self.rag.get_stats()
        self.assertEqual(stats["total_documents"], 2)
        self.assertEqual(stats["conversation_documents"], 1)
        
        # Test export
        json_export = self.rag.export_data("json")
        self.assertIn("documents", json_export)
        
        txt_export = self.rag.export_data("txt")
        self.assertIn("STATISTICS:", txt_export)


class TestAgentCoordination(unittest.TestCase):
    """Test Agent Coordination system."""
    
    def setUp(self):
        """Set up test environment."""
        self.coordinator = AgentCoordinator()
        self.enhanced_jarvis = EnhancedJARVIS()
    
    def tearDown(self):
        """Clean up test environment."""
        self.coordinator.shutdown()
        self.enhanced_jarvis.coordinator.shutdown()
    
    def test_agent_registration(self):
        """Test agent registration."""
        initial_count = len(self.coordinator.agents)
        
        # Agents should be automatically registered
        self.assertGreater(initial_count, 0)
        
        # Check specific agents
        agent_types = [agent.agent_type.name for agent in self.coordinator.agents.values()]
        self.assertIn("PLANNER", agent_types)
        self.assertIn("EXECUTOR", agent_types)
        self.assertIn("MONITOR", agent_types)
    
    def test_task_creation_and_assignment(self):
        """Test task creation and assignment."""
        # Create a task
        task_id = self.coordinator.create_task(
            "Test task for agent system",
            TaskPriority.NORMAL
        )
        
        self.assertIsNotNone(task_id)
        self.assertIn(task_id, self.coordinator.tasks)
        
        # Check task is in queue
        self.assertGreater(len(self.coordinator.task_queue), 0)
    
    def test_enhanced_jarvis_processing(self):
        """Test enhanced JARVIS request processing."""
        # Process a simple request
        result = self.enhanced_jarvis.process_request(
            "Test request for enhanced system"
        )
        
        self.assertIsNotNone(result)
        self.assertIn("task_id", result)
        self.assertIn("state", result)
    
    def test_system_status(self):
        """Test system status reporting."""
        status = self.enhanced_jarvis.get_status()
        
        self.assertIn("coordinator_status", status)
        self.assertIn("agents", status["coordinator_status"])
        self.assertIn("tasks", status["coordinator_status"])
        self.assertIn("performance", status["coordinator_status"])


class TestIntegratedSystem(unittest.TestCase):
    """Test integrated system functionality."""
    
    def setUp(self):
        """Set up integrated test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Set up conversation config
        self.conv_config = ConversationConfig(history_folder=self.temp_dir)
        self.conversation = JARVISConversation(config=self.conv_config)
        
        # Set up RAG config
        self.rag_config = RAGConfig(
            storage_path=os.path.join(self.temp_dir, "rag"),
            embedding_backend="none"
        )
        self.rag = RAGSystem(self.rag_config)
        
        # Enhanced JARVIS
        self.enhanced_jarvis = EnhancedJARVIS()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.enhanced_jarvis.coordinator.shutdown()
    
    def test_conversation_with_rag_integration(self):
        """Test conversation system integrated with RAG."""
        # Add some context to RAG
        self.rag.add_conversation_memory(
            "What is machine learning?",
            "Machine learning is a subset of AI that enables computers to learn from data."
        )
        
        # Generate enhanced prompt
        enhanced_prompt = self.rag.generate_context_prompt(
            "Tell me more about machine learning applications"
        )
        
        self.assertIn("machine learning", enhanced_prompt.lower())
        self.assertIn("context", enhanced_prompt.lower())
    
    def test_agent_rag_coordination(self):
        """Test coordination between agents and RAG system."""
        # Add knowledge to RAG
        self.rag.add_document(
            "Python is great for web development with frameworks like Django and Flask",
            {"topic": "web_development"}
        )
        
        # Process request through enhanced system
        result = self.enhanced_jarvis.process_request(
            "I want to learn about Python web development"
        )
        
        self.assertIsNotNone(result)
        # Should complete successfully
        self.assertNotEqual(result["state"], "ERROR")
    
    def test_memory_persistence(self):
        """Test memory persistence across sessions."""
        # Add memory
        self.rag.add_conversation_memory(
            "My name is Alice",
            "Nice to meet you, Alice!"
        )
        
        # Simulate system restart by creating new RAG instance
        new_rag = RAGSystem(self.rag_config)
        
        # Check if memory persists
        results = new_rag.retrieve_context("Alice")
        self.assertGreater(len(results), 0)
        
        alice_found = any("alice" in r.document.content.lower() for r in results)
        self.assertTrue(alice_found)
    
    def test_error_handling(self):
        """Test system error handling."""
        # Test with invalid task
        result = self.enhanced_jarvis.process_request("")
        
        # Should handle gracefully
        self.assertIsNotNone(result)
        
        # Test RAG with invalid query
        results = self.rag.retrieve_context("")
        self.assertIsInstance(results, list)


class TestPerformance(unittest.TestCase):
    """Test system performance characteristics."""
    
    def setUp(self):
        """Set up performance test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = RAGConfig(
            storage_path=os.path.join(self.temp_dir, "perf_test"),
            embedding_backend="none"
        )
        self.rag = RAGSystem(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_large_document_handling(self):
        """Test handling of many documents."""
        import time
        
        # Add many documents
        start_time = time.time()
        
        for i in range(100):
            self.rag.add_document(
                f"Test document {i} with content about topic {i % 10}",
                {"id": i, "topic": i % 10}
            )
        
        add_time = time.time() - start_time
        
        # Should be reasonably fast (under 5 seconds for 100 docs)
        self.assertLess(add_time, 5.0)
        
        # Test retrieval performance
        start_time = time.time()
        results = self.rag.retrieve_context("topic")
        retrieval_time = time.time() - start_time
        
        # Should find results quickly
        self.assertLess(retrieval_time, 1.0)
        self.assertGreater(len(results), 0)
    
    def test_memory_usage(self):
        """Test memory usage patterns."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Add many documents
        for i in range(1000):
            self.rag.add_document(f"Document {i}", {"id": i})
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 1000 docs)
        self.assertLess(memory_increase, 100 * 1024 * 1024)


def run_comprehensive_tests():
    """Run all tests with detailed output."""
    print("🧪 Running Enhanced JARVIS System Tests")
    print("=" * 50)
    
    # Create test suite
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestRAGSystem,
        TestAgentCoordination,
        TestIntegratedSystem,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = test_loader.loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)