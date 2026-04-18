# JARVIS 2.0 - Fully Agentic AI Assistant

JARVIS 2.0 is a fully agentic AI assistant with Claude Code-style coding capabilities and Claude Coworker-style knowledge work features. It supports multiple LLM providers with a text-first interface and future voice extensibility.

## Features

- **Multi-LLM Provider Support**: OpenAI (GPT-4, GPT-4o) and Anthropic (Claude 3.5, Claude 4) with easy plugin system for adding new providers
- **Agentic Capabilities**: Specialized agents for coding (Claude Code style) and knowledge work (Claude Coworker style) with intelligent task coordination
- **Tool System**: Extensible plugin architecture with file operations (read, write, list, search), code execution (Python, shell), and document processing (PDF, summarization, data extraction)
- **Semantic Memory**: Long-term memory with embeddings and importance-based retention using sentence-transformers
- **Enhanced RAG**: Hybrid retrieval system combining semantic and keyword search with document indexing
- **Safety Layer**: Permission system, checkpoint/undo functionality, and destructive action detection
- **Conversation Management**: Context-aware conversation history with automatic trimming and token limit optimization
- **Text-First Interface**: CLI interface with help, status, and tool listing commands

## Architecture

```
JARVIS 2.0/
├── core/
│   ├── llm/              # LLM provider abstraction
│   ├── agents/           # Agent system
│   ├── tools/            # Tool system
│   ├── memory/           # Semantic memory
│   ├── rag/              # RAG system
│   ├── safety/           # Safety manager
│   └── config/           # Configuration
├── interface/
│   ├── cli/              # Command-line interface
│   └── web_ui/           # Web interface (future)
├── plugins/
│   ├── providers/        # Custom LLM providers
│   └── tools/            # Custom tools
└── tests/                # Test suite
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd JARVIS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```

4. Edit `.env` file and add your API keys:
```env
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Usage

### Running JARVIS

```bash
python -m interface.cli.cli
```

Or create a main.py entry point:
```python
from interface.cli.cli import main

if __name__ == "__main__":
    main()
```

### CLI Commands

- `help` - Show help information
- `status` - Display system status
- `providers` - List configured LLM providers
- `tools` - List available tools
- `exit` / `quit` - Exit JARVIS

### Basic Usage

```
JARVIS > help
JARVIS > status
JARVIS > What can you help me with?
```

## Implementation Status

**All core phases (1-4) are now complete!** The system includes:

- ✅ LLM Provider Abstraction with OpenAI and Anthropic support
- ✅ Configuration management with environment variables
- ✅ Tool system with 9 built-in tools (file, code, document operations)
- ✅ Agent system with Coding Agent and Knowledge Agent
- ✅ Agent Coordinator for intelligent task routing
- ✅ Semantic Memory with embedding support
- ✅ Enhanced RAG with hybrid retrieval
- ✅ Conversation Manager for context tracking
- ✅ Safety Manager with checkpoints and permission system
- ✅ CLI interface with integrated agents and tools

The system is ready for use. Configure your API keys in `.env` and run `python main.py` to start.

## Configuration

Configuration is managed through environment variables in the `.env` file:

- `DEFAULT_PROVIDER` - Default LLM provider (openai or anthropic)
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `DEBUG` - Enable debug mode
- `REQUIRE_CONFIRMATION` - Require confirmation for destructive actions
- `AUTO_CHECKPOINT` - Automatically create checkpoints

## Adding Custom Providers

Create a new provider plugin in `plugins/providers/`:

```python
from core.llm.base import BaseLLMProvider

class CustomProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate(self, messages, model, **kwargs):
        # Implementation
        pass
    
    async def generate_with_tools(self, messages, tools, model, **kwargs):
        # Implementation
        pass
    
    def get_available_models(self):
        return ["model1", "model2"]
    
    def validate_api_key(self):
        return bool(self.api_key)
```

Then register it in your code:
```python
from core.llm.registry import LLMProviderRegistry
from plugins.providers.custom_provider import CustomProvider

registry = LLMProviderRegistry()
provider = CustomProvider(api_key="your-key")
registry.register("custom", provider)
```

## Adding Custom Tools

Create a new tool plugin in `plugins/tools/`:

```python
from core.tools.base import BaseTool, ToolInput, ToolOutput

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "A custom tool"
    input_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string"}
        },
        "required": ["param1"]
    }
    
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Implementation
        return ToolOutput(
            success=True,
            result="Result",
        )
```

Register the tool:
```python
from core.tools.registry import ToolRegistry
from plugins.tools.custom_tool import CustomTool

registry = ToolRegistry()
tool = CustomTool()
registry.register(tool)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black core/
ruff check core/
```

## Roadmap

### Phase 1: Foundation ✅ COMPLETED
- [x] LLM Provider Abstraction Layer
- [x] Configuration System
- [x] Tool System Foundation
- [x] Basic CLI Interface

### Phase 2: Core Agents ✅ COMPLETED
- [x] Base Agent Architecture
- [x] Coding Agent (Claude Code style)
- [x] Knowledge Agent (Claude Coworker style)
- [x] Agent Coordinator

### Phase 3: Memory & Context ✅ COMPLETED
- [x] Semantic Memory System
- [x] Enhanced RAG System
- [x] Conversation Manager

### Phase 4: Safety & Advanced Features ✅ COMPLETED
- [x] Safety Manager
- [x] Checkpoint/Undo System
- [x] Advanced Tool Implementations

### Future Extensions
- [ ] Voice Interface Plugin
- [ ] Web Search Tool
- [ ] Web UI
- [ ] Mobile App
- [ ] Advanced Agents
- [ ] Collaboration Features
- [ ] Cloud Sync

## License

[Your License Here]

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## Support

For issues and questions, please open an issue on GitHub.
