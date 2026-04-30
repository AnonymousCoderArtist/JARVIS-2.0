# JARVIS 2.0 - Fully Agentic AI Assistant

JARVIS 2.0 is a fully agentic AI assistant with Claude Code-style coding capabilities and Claude Coworker-style knowledge work features. It features a rich CLI interface with streaming assistant output, tool calls, slash commands, and provider/model status.

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
pip install -e .
```

3. (Optional) Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` file to set your provider configuration:
```env
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=your_api_key_here
JARVIS_SDK=openai
```

## Usage

### Running JARVIS

JARVIS now uses CLI flags for configuration. You can run it with:

```bash
# Using CLI flags
jarvis --cli --model gpt-4o --base_url https://api.openai.com/v1 --apikey YOUR_KEY --sdk openai

# Using .env file (if configured)
jarvis --cli

# Using short flags
jarvis --cli -m gpt-4o --apikey YOUR_KEY
```

**Available CLI Flags:**
- `--model, -m`: Model name (e.g., gpt-4o, claude-3-5-sonnet-20241022)
- `--base_url`: Base URL for the LLM API
- `--apikey, --api-key`: API key for the LLM provider
- `--sdk`: SDK mode (openai, anthropic, standard)
- `--cli`: Launch the Rich CLI

### CLI Commands

Once JARVIS is running, you can use these commands:

- `/help` - Show help information
- `/status` - Display system status
- `/clear` - Clear the screen
- `/exit` - Exit JARVIS
- `! <cmd>` - Run shell command

### Basic Usage

```
JARVIS > /help
JARVIS > /status
JARVIS > What can you help me with?
JARVIS > ! ls -la
```

## Implementation Status

**All core phases (1-4) are now complete!** The system includes:

- ✅ LLM Provider Abstraction with OpenAI and Anthropic support
- ✅ Configuration management with environment variables
- ✅ Tool system with 9 built-in tools (file, code, document operations)
- ✅ Single JARVIS agent with comprehensive capabilities
- ✅ Dynamic tool description injection (OpenClaude style)
- ✅ Semantic Memory with embedding support
- ✅ Enhanced RAG with hybrid retrieval
- ✅ Conversation Manager for context tracking
- ✅ Safety Manager with checkpoints and permission system
- ✅ CLI interface with integrated agent and tools

The system is ready for use. Run JARVIS with CLI flags or configure a `.env` file for convenience.

## Configuration

JARVIS uses CLI flags for configuration, with optional support for `.env` files. The old `config.toml` and `providers.json` files are no longer required.

**CLI Flags (take precedence):**
```bash
jarvis --cli --model gpt-4o --base_url https://api.openai.com/v1 --apikey YOUR_KEY --sdk openai
```

**Environment Variables (.env):**
```env
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=your_api_key_here
JARVIS_SDK=openai

# Token Limits (optional)
# Default: 128K total context (109K input + 16K output)
# 1K = 1024 tokens
JARVIS_MAX_CONTEXT_TOKENS=131072
JARVIS_MAX_INPUT_TOKENS=111616
JARVIS_MAX_OUTPUT_TOKENS=16384
```

**Configuration Priority:**
1. CLI flags (highest priority)
2. .env file values
3. Default values (gpt-4o, openai SDK)

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
- [x] JARVIS Agent (unified coding and knowledge capabilities)
- [x] Dynamic tool description injection
- [x] Agentic tool calling and error recovery

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
