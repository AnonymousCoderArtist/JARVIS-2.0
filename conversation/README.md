# JARVIS Enhanced Conversation System

An advanced conversation management system for JARVIS with improved prompt generation, optional embedding support, and enhanced memory management.

## Features

### 🧠 Enhanced Memory Management
- **Persistent Memory**: Stores important conversation details across sessions
- **Intelligent Filtering**: Automatically determines memory-worthy content
- **Importance Scoring**: Prioritizes memories by relevance and importance
- **Semantic Search**: Find relevant memories using embeddings or keywords

### 🔍 Optional Embedding Support
Choose from multiple embedding backends:
- **None**: Traditional keyword-based search (always available)
- **Sentence Transformers**: Local embedding generation using Hugging Face models
- **OpenAI Embeddings**: Cloud-based embeddings via OpenAI API

### 🎯 Improved Prompt Generation
- **Context-Aware Prompts**: Incorporates relevant conversation history
- **Memory Integration**: Includes relevant past interactions
- **Adaptive Context**: Intelligently trims content to fit token limits
- **Tool Integration**: Enhanced prompts for tool-based responses

### 🔧 Better Tool Calling
- **Smart Tool Selection**: Improved AI reasoning for tool choice
- **Error Handling**: Graceful fallbacks and retry logic
- **Multi-tool Support**: Intelligent chaining of multiple tools
- **Enhanced Feedback**: Better explanation of tool usage and results

## Installation

### Basic Setup
The enhanced conversation system works out of the box with keyword-based search:

```python
from conversation import JARVISConversation
from conversation.config import ConversationConfig, EmbeddingBackend

# Basic configuration (no embeddings)
config = ConversationConfig()
conversation = JARVISConversation(name="YourName", config=config)
```

### Optional Dependencies

#### For Sentence Transformers Support
```bash
pip install sentence-transformers
```

#### For OpenAI Embeddings Support
```bash
pip install openai
```

## Configuration

### Embedding Backends

#### No Embeddings (Default)
```python
from conversation.config import EmbeddingConfig, EmbeddingBackend

config = ConversationConfig()
config.embedding = EmbeddingConfig(backend=EmbeddingBackend.NONE)
```

#### Sentence Transformers
```python
config.embedding = EmbeddingConfig(
    backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
    model_name="all-MiniLM-L6-v2",  # or other compatible models
    similarity_threshold=0.7,
    max_results=5
)
```

#### OpenAI Embeddings
```python
config.embedding = EmbeddingConfig(
    backend=EmbeddingBackend.OPENAI,
    model_name="text-embedding-ada-002",
    api_key="your-openai-api-key",
    similarity_threshold=0.7,
    max_results=5
)
```

### Advanced Configuration
```python
config = ConversationConfig(
    max_tokens=8000,
    history_offset=10250,
    save_interval=300,  # 5 minutes
    max_memory_entries=100,
    history_folder="History",
    embedding=EmbeddingConfig(...)
)
```

## Usage Examples

### Basic Conversation
```python
from conversation import JARVISConversation

# Initialize conversation
conversation = JARVISConversation(name="Alice")

# Add messages
conversation.add_message("User", "Hello JARVIS")
conversation.add_message("JARVIS", "Hello Alice! How can I help you today?")

# Generate enhanced prompts
prompt = conversation.generate_complete_prompt("What's the weather like?")
```

### Tool Integration
```python
# Process a complete interaction with tools
user_input = "Search for Python tutorials"
ai_response = "I found several excellent Python tutorials for you."
tool_outputs = [
    {
        "name": "websearch",
        "output": "Found 10 Python tutorial websites",
        "arguments": {"query": "Python tutorials"}
    }
]

# This automatically handles memory creation, context tracking, etc.
conversation.process_interaction(user_input, ai_response, tool_outputs)
```

### Memory Management
```python
# Add important memories manually
memory_id = conversation.memory_manager.add_memory(
    content="User prefers Python for machine learning projects",
    metadata={"type": "preference", "domain": "programming"},
    importance=0.8
)

# Search memories
relevant_memories = conversation.memory_manager.search_memories("programming")

# Get memory statistics
stats = conversation.memory_manager.get_stats()
```

### Conversation Export
```python
# Export conversation as JSON
json_data = conversation.export_conversation("json")

# Export as plain text
text_data = conversation.export_conversation("txt")
```

## Architecture

### File Structure
```
conversation/
├── __init__.py           # Package initialization
├── config.py            # Configuration classes
├── core.py              # Main conversation management
├── embeddings.py        # Embedding providers and management
├── memory.py            # Memory management system
└── prompt_optimizer.py  # Prompt generation and optimization
```

### Key Components

#### JARVISConversation (core.py)
- Main conversation management class
- Handles message flow and context
- Coordinates between components

#### MemoryManager (memory.py)
- Persistent memory storage
- Semantic and keyword search
- Importance-based filtering

#### EmbeddingManager (embeddings.py)
- Multiple embedding backends
- Similarity calculations
- Embedding storage and retrieval

#### PromptOptimizer (prompt_optimizer.py)
- Context-aware prompt generation
- Memory integration
- Token limit management

## File Storage

The system creates the following files in the `History/` folder:
- `JARVISConversation_history.txt`: Main conversation log
- `chat.txt`: Real-time chat buffer
- `memory.txt`: Legacy memory file (still supported)
- `embeddings.json`: Embedding database

## Performance Considerations

### Memory Usage
- Memories are automatically cleaned up when limit is reached
- Embeddings are cached locally to avoid re-computation
- Conversation history is intelligently trimmed

### Embedding Performance
- **Sentence Transformers**: Fast local inference, one-time model download
- **OpenAI**: Fast API calls but requires internet and API credits
- **None**: Instant keyword matching, no external dependencies

## Migration from Legacy System

The enhanced system is backward compatible with the original `EXTRA/conversation.py`:

```python
# Old way
from EXTRA.conversation import JARVISConversation
conversation = JARVISConversation()

# New way
from conversation import JARVISConversation
conversation = JARVISConversation()
```

Existing conversation files and data will be automatically loaded and migrated.

## Testing

Run the test suite to verify functionality:

```bash
# Basic functionality tests
python test_conversation.py

# Embedding functionality demo
python demo_embeddings.py
```

## Troubleshooting

### Common Issues

#### Import Errors
- Ensure the `conversation` folder is in your Python path
- Check that all required dependencies are installed

#### Embedding Issues
- **Sentence Transformers**: First run may be slow due to model download
- **OpenAI**: Verify API key is set correctly and has sufficient credits
- **Performance**: Consider using lighter models for faster inference

#### Memory Issues
- Adjust `max_memory_entries` in configuration for memory constraints
- Clear old embeddings if storage becomes an issue

### Debug Mode
Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When extending the conversation system:
1. Follow the existing architecture patterns
2. Add comprehensive tests for new features
3. Update this documentation
4. Ensure backward compatibility

## Changelog

### Version 2.0.0
- Complete rewrite with modular architecture
- Added optional embedding support (Sentence Transformers, OpenAI)
- Enhanced memory management with importance scoring
- Improved prompt generation with context awareness
- Better tool integration and error handling
- Backward compatibility with legacy system