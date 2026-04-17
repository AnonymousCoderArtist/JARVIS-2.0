# JARVIS Architecture Documentation

## Overview

JARVIS (Just A Rather Very Intelligent System) is an advanced AI assistant with a modular, agentic architecture designed for intelligent task planning, execution, and coordination. The system features semantic memory, RAG (Retrieval Augmented Generation), multi-agent coordination, and comprehensive tool integration.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         JARVIS Main System                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Main Entry Point                      │  │
│  │                       (main.py)                          │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                       │
│  ┌──────────────────────┼───────────────────────────────────┐  │
│  │                      │                                   │  │
│  │  ┌──────────────────▼──────────────────┐                │  │
│  │  │       Conversation System           │                │  │
│  │  │  (conversation/)                    │                │  │
│  │  │  - JARVISConversation               │                │  │
│  │  │  - MemoryManager                    │                │  │
│  │  │  - EmbeddingManager                │                │  │
│  │  │  - PromptOptimizer                 │                │  │
│  │  └──────────────────┬──────────────────┘                │  │
│  │                     │                                     │  │
│  │  ┌──────────────────▼──────────────────┐                │  │
│  │  │         RAG System                  │                │  │
│  │  │      (rag_system.py)                │                │  │
│  │  │  - DocumentIndexer                 │                │  │
│  │  │  - SemanticRetriever               │                │  │
│  │  │  - KeywordRetriever                │                │  │
│  │  │  - HybridRetriever                 │                │  │
│  │  └──────────────────┬──────────────────┘                │  │
│  │                     │                                     │  │
│  │  ┌──────────────────▼──────────────────┐                │  │
│  │  │      Agent Coordination             │                │  │
│  │  │       (AGENTS/)                     │                │  │
│  │  │  - FunctionCallingAgent             │                │  │
│  │  │  - EnhancedJARVIS                   │                │  │
│  │  │  - AgentCoordinator                │                │  │
│  │  │  - TASKFORGE                        │                │  │
│  │  └──────────────────┬──────────────────┘                │  │
│  │                     │                                     │  │
│  │  ┌──────────────────▼──────────────────┐                │  │
│  │  │         Tool System                 │                │  │
│  │  │         (TOOL/)                     │                │  │
│  │  │  - Web Search (Felo)                │                │  │
│  │  │  - Website Analysis                 │                │  │
│  │  │  - PDF Processing                   │                │  │
│  │  │  - News Retrieval                   │                │  │
│  │  │  - Internet Speed                   │                │  │
│  │  └──────────────────┬──────────────────┘                │  │
│  │                     │                                     │  │
│  │  ┌──────────────────▼──────────────────┐                │  │
│  │  │      Supporting Systems             │                │  │
│  │  │  - Dataset Builder                  │                │  │
│  │  │  - Configuration                    │                │  │
│  │  │  - JPrinter Utilities               │                │  │
│  │  └─────────────────────────────────────┘                │  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Main Entry Point (main.py)

The main entry point orchestrates all system components and provides the user interface.

**Key Responsibilities:**
- Initialize all subsystems (conversation, RAG, agents, tools)
- Handle user input and route to appropriate systems
- Coordinate between different AI agents
- Manage tool execution and response generation
- Provide system status and export functionality

**Class Structure:**
```python
class JARVIS:
    def __init__(self):
        self.dataset_builder = DatasetBuilder()
        self.conversation = JARVISConversation()
        self.rag_system = RAGSystem()
        self.enhanced_jarvis = EnhancedJARVIS()
        self.agent = FunctionCallingAgent()
        self.ai = C4ai()
    
    def execute_tool_and_respond(self, user_input: str)
    def process_with_rag(self, user_input: str) -> str
    def show_system_status(self)
    def export_all_data(self, format_type: str)
```

### 2. Conversation System (conversation/)

A sophisticated conversation management system with semantic memory and context-aware responses.

```
conversation/
├── __init__.py           # Package initialization
├── core.py              # Main conversation management
├── memory.py            # Semantic memory system
├── embeddings.py        # Multiple embedding backends
├── prompt_optimizer.py  # Intelligent prompt generation
└── config.py            # Configuration management
```

#### 2.1 JARVISConversation (core.py)

The core conversation handler that manages chat history, context, and responses.

**Key Features:**
- Conversation history management with automatic trimming
- Context-aware prompt generation
- Integration with memory and embedding systems
- Real-time chat buffer with periodic summarization
- Importance-based message filtering

**Data Flow:**
```
User Input → Generate Complete Prompt → Add to History → Trim if Needed → Return Prompt
                ↓
         Include Memory Context
         Include Embeddings
         Optimize for Token Limits
```

#### 2.2 MemoryManager (memory.py)

Semantic memory system that stores and retrieves important conversation context.

**Key Features:**
- Importance-based memory storage
- Semantic search using embeddings
- Temporal awareness (recency and frequency)
- Automatic memory cleanup
- Context retrieval for relevant queries

**Memory Structure:**
```python
@dataclass
class Memory:
    content: str
    importance: float  # 0.0 to 1.0
    timestamp: datetime
    embedding: Optional[List[float]]
    metadata: Dict[str, Any]
```

#### 2.3 EmbeddingManager (embeddings.py)

Multiple embedding backend support for semantic search.

**Supported Backends:**
- **NONE**: Keyword-based search (no embeddings)
- **SENTENCE_TRANSFORMERS**: Local embeddings using sentence-transformers
- **OPENAI**: Cloud-based OpenAI embeddings (requires API key)

**Architecture:**
```
EmbeddingManager
    ├── SentenceTransformerBackend
    │   └── Uses all-MiniLM-L6-v2 model
    ├── OpenAIBackend
    │   └── Uses text-embedding-ada-002
    └── NoneBackend
        └── Keyword matching only
```

#### 2.4 PromptOptimizer (prompt_optimizer.py)

Intelligent prompt generation and optimization.

**Key Functions:**
- Token limit optimization
- Context prioritization
- Memory integration
- RAG context enhancement
- Tool response formatting

### 3. RAG System (rag_system.py)

Comprehensive Retrieval Augmented Generation system for intelligent context retrieval.

```
RAG System Architecture:

┌─────────────────────────────────────────────────────────┐
│                    RAGSystem                              │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │          DocumentIndexer                         │  │
│  │  - add_document()                                │  │
│  │  - update_document()                             │  │
│  │  - remove_document()                             │  │
│  │  - search_documents()                            │  │
│  │  - Keyword Index Building                        │  │
│  └──────────────────────────────────────────────────┘  │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         HybridRetriever                           │  │
│  │  ┌──────────────────────────────────────────┐   │  │
│  │  │  SemanticRetriever (Embedding-based)    │   │  │
│  │  │  - Cosine similarity matching            │   │  │
│  │  │  - Threshold filtering                   │   │  │
│  │  └──────────────────────────────────────────┘   │  │
│  │  ┌──────────────────────────────────────────┐   │  │
│  │  │  KeywordRetriever (TF-IDF-like)          │   │  │
│  │  │  - Term frequency scoring                │   │  │
│  │  │  - Tokenization and matching             │   │  │
│  │  └──────────────────────────────────────────┘   │  │
│  │  - Result fusion and re-ranking                  │  │
│  └──────────────────────────────────────────────────┘  │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Context Generation                           │  │
│  │  - generate_context_prompt()                     │  │
│  │  - Length-aware truncation                      │  │
│  │  - Source attribution                           │  │
│  └──────────────────────────────────────────────────┘  │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Key Classes:**

#### DocumentIndexer
Manages document storage, indexing, and retrieval.

```python
class DocumentIndexer:
    def add_document(self, content: str, metadata: Dict) -> str
    def update_document(self, doc_id: str, content: str, metadata: Dict) -> bool
    def remove_document(self, doc_id: str) -> bool
    def search_documents(self, query: str, limit: int) -> List[str]
    def get_stats(self) -> Dict[str, Any]
```

#### SemanticRetriever
Embedding-based semantic search.

```python
class SemanticRetriever:
    def retrieve(self, query: str, limit: int) -> List[RetrievalResult]
    def _calculate_similarity(self, emb1: List[float], emb2: List[float]) -> float
```

#### KeywordRetriever
Keyword-based retrieval as fallback.

```python
class KeywordRetriever:
    def retrieve(self, query: str, limit: int) -> List[RetrievalResult]
    def _calculate_keyword_score(self, query: str, content: str) -> float
```

#### HybridRetriever
Combines semantic and keyword retrieval with re-ranking.

```python
class HybridRetriever:
    def retrieve(self, query: str, limit: int) -> List[RetrievalResult]
    def _rerank_results(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]
```

### 4. Agent Coordination System (AGENTS/)

Multi-agent architecture for intelligent task planning and execution.

```
AGENTS/
├── __init__.py           # Package initialization
├── functioncall.py       # Function calling agent
├── coordinator.py        # Agent coordination system
├── taskforge.py          # Task planning and decomposition
└── proxy.py             # Proxy management for API calls
```

#### 4.1 FunctionCallingAgent (functioncall.py)

Intelligent tool selection and execution using function calling.

**Architecture:**
```
User Request → FunctionCallingAgent → Parse Intent → Select Tools → Execute → Return Results
                    ↓
            System Prompt Generation
                    ↓
            Tool Description Injection
                    ↓
            JSON Response Parsing
                    ↓
            Tool Execution with Error Handling
```

**Key Components:**
- Tool registration and discovery
- Intent analysis and tool selection
- Retry logic with clarification
- Fallback to general AI when no tools match
- Error handling and graceful degradation

**Tool Definition Format:**
```python
@tools
def websearch(query: str) -> str:
    """Search the web for current information"""
    return f"Searching for '{query}'"
```

#### 4.2 EnhancedJARVIS & AgentCoordinator (coordinator.py)

Multi-agent coordination system for complex task handling.

**Agent Types:**
```
BaseAgent (Abstract)
    ├── PlannerAgent
    │   └── Task decomposition and planning
    ├── ExecutorAgent
    │   └── Function calling and tool execution
    ├── MonitorAgent
    │   └── System health monitoring
    └── SpecialistAgent
        └── Domain-specific expertise (Python, AI, etc.)
```

**Agent Coordinator Flow:**
```
User Request → Create Task → Priority Queue → Assign to Agent → Execute → Monitor → Return Result
                    ↓
              Dependency Analysis
                    ↓
              Agent Selection (Capability + Performance)
                    ↓
              Parallel Execution (ThreadPoolExecutor)
                    ↓
              Result Aggregation
```

**Task Lifecycle:**
```
Task States:
IDLE → PLANNING → EXECUTING → WAITING → COMPLETED
                    ↓
                  ERROR
                    ↓
                 CANCELLED
```

#### 4.3 TASKFORGE (taskforge.py)

Task planning and decomposition system.

**Key Functions:**
- Break down complex requests into actionable steps
- Generate action plans with dependencies
- Estimate execution time and resource requirements
- Handle task failures with recovery strategies

**Action Plan Structure:**
```python
@dataclass
class ActionPlan:
    steps: List[Step]
    dependencies: Dict[str, List[str]]
    estimated_time: float
    confidence: float
```

#### 4.4 ProxyManager (proxy.py)

Proxy rotation and management for API calls.

**Features:**
- Automatic proxy rotation
- Health checking
- Error recovery
- Rate limiting
- Session management

### 5. Tool System (TOOL/)

Comprehensive tool integration for various capabilities.

```
TOOL/
├── __init__.py           # Package initialization
├── main.py              # Tool registration and exports
├── askwebsite.py        # Website content extraction
├── internetspeed.py     # Internet speed testing
├── news.py              # News retrieval
└── pdf.py               # PDF processing
```

#### 5.1 Web Search (via RESEARCH/felo.py)

Research-grade web search using Felo AI.

**Features:**
- Streaming responses
- Citation management
- Search result formatting
- Timeout handling
- Error recovery

**Integration:**
```python
from RESEARCH.felo import Felo, DefaultResponseFormatter

@tools
def websearch(query: str, timeout: int = 30, stream: bool = False) -> str:
    felo_agent = Felo(timeout=timeout, formatter=DefaultResponseFormatter())
    return felo_agent.chat(query, stream=stream)
```

#### 5.2 Website Analysis (askwebsite.py)

Extract and analyze content from websites.

**Features:**
- HTML to text conversion
- Link and image filtering
- Markdown output support
- Page break detection
- Error handling

**Configuration:**
```python
@dataclass
class WebsiteConfig:
    url: str
    ignore_links: bool
    ignore_images: bool
    output_format: OutputFormat
    output_mode: OutputMode
    output_path: str
    show_page_breaks: bool
```

#### 5.3 PDF Processing (pdf.py)

Extract and process PDF documents.

**Features:**
- Text extraction from PDFs
- Page-by-page processing
- Output formatting options
- Error handling for corrupted files

#### 5.4 News Retrieval (news.py)

Get latest news on specific topics.

**Features:**
- Topic-based news search
- Result limiting
- Multiple source aggregation
- Date filtering

#### 5.5 Internet Speed Testing (internetspeed.py)

Test internet connection speed and quality.

**Features:**
- Download speed measurement
- Upload speed measurement
- Ping latency testing
- Error handling for firewall issues

### 6. Dataset Builder (dataset.py)

Comprehensive dataset management for training and analysis.

**Features:**
- Multiple format support (JSON, CSV, Parquet, XML, JSONL, Excel, SQLite)
- Data validation and cleaning
- Data augmentation
- HuggingFace Dataset integration
- Statistical analysis

**Key Operations:**
```python
dataset = DatasetBuilder(filepath="tool_usage.json")

# Add data
dataset.add_datapoint(user_input="...", tool_calls=[...], response="...")

# Export
dataset.export_to_csv("output.csv")
dataset.export_to_parquet("output.parquet")

# Analysis
stats = dataset.get_statistics()

# HuggingFace integration
hf_dataset = dataset.create_hf_dataset()
```

### 7. Configuration System (config/)

Centralized configuration management.

**Configuration Structure:**
```python
class Config:
    # File Paths
    HISTORY_FOLDER: str = "History"
    DATASET_FILE: str = "tool_usage.json"
    
    # Conversation Settings
    MAX_TOKENS: int = 8000
    HISTORY_OFFSET: int = 10250
    SAVE_INTERVAL: int = 300
    
    # User Settings
    DEFAULT_USER: str = "Vortex"
```

### 8. JPrinter Utilities (jprinter/)

Advanced printing and debugging utilities.

**Features:**
- Beautiful console output
- Syntax highlighting
- Debug information
- Color themes
- Variable inspection

## Data Flow Diagrams

### Complete Request Processing Flow

```
┌──────────────┐
│ User Input   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                  JARVIS Main System                      │
└──────────────────────┬──────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────────┐ ┌──────────┐ ┌─────────────┐
│ RAG System   │ │ Conv.    │ │ Agent Coord │
│ (Context)    │ │ (Memory) │ │ (Planning)  │
└──────┬───────┘ └────┬─────┘ └──────┬──────┘
       │              │              │
       └──────────────┼──────────────┘
                      ▼
           ┌────────────────────┐
           │ Enhanced Prompt     │
           └──────────┬─────────┘
                      │
                      ▼
           ┌────────────────────┐
           │ Function Call Agent│
           └──────────┬─────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    ┌────────┐  ┌─────────┐  ┌────────┐
    │ Web    │  │ PDF     │  │ News   │
    │ Search │  │ Process │  │ Fetch  │
    └───┬────┘  └────┬────┘  └───┬────┘
        │            │            │
        └────────────┼────────────┘
                     │
                     ▼
           ┌────────────────────┐
           │ Tool Outputs       │
           └──────────┬─────────┘
                      │
                      ▼
           ┌────────────────────┐
           │ AI Response Gen    │
           └──────────┬─────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    ┌────────┐  ┌─────────┐  ┌────────┐
    │ Conv.  │  │ RAG     │  │Dataset │
    │ History│  │ Storage │  │ Builder│
    └────────┘  └─────────┘  └────────┘
                      │
                      ▼
           ┌────────────────────┐
           │ User Response      │
           └────────────────────┘
```

### RAG Integration Flow

```
┌──────────────┐
│ User Query   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────┐
│ RAG System                     │
│                                │
│  ┌─────────────────────────┐  │
│  │ HybridRetriever         │  │
│  │  ┌───────────────────┐  │  │
│  │  │ Semantic Search  │  │  │
│  │  │ (Embeddings)     │  │  │
│  │  └────────┬──────────┘  │  │
│  │           │              │  │
│  │  ┌────────▼──────────┐  │  │
│  │  │ Keyword Search    │  │  │
│  │  │ (TF-IDF-like)     │  │  │
│  │  └────────┬──────────┘  │  │
│  │           │              │  │
│  │  ┌────────▼──────────┐  │  │
│  │  │ Result Fusion     │  │  │
│  │  │ & Re-ranking      │  │  │
│  │  └────────┬──────────┘  │  │
│  └───────────┼──────────────┘  │
│              │                 │
│  ┌───────────▼──────────────┐  │
│  │ Context Generation       │  │
│  │ - Add retrieved docs     │  │
│  │ - Truncate to limit      │  │
│  │ - Add source info        │  │
│  └───────────┬──────────────┘  │
└──────────────┼──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Enhanced Prompt                │
│ (with RAG context)             │
└─────────────────────────────────┘
```

### Agent Coordination Flow

```
┌──────────────┐
│ Complex Task │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────┐
│ AgentCoordinator               │
│                                │
│  ┌─────────────────────────┐  │
│  │ Task Creation           │  │
│  │ - Priority assignment   │  │
│  │ - Dependency analysis   │  │
│  └───────────┬──────────────┘  │
│              │                 │
│  ┌───────────▼──────────────┐  │
│  │ Agent Selection         │  │
│  │ - Capability matching   │  │
│  │ - Performance scoring   │  │
│  │ - Availability check    │  │
│  └───────────┬──────────────┘  │
│              │                 │
│  ┌───────────▼──────────────┐  │
│  │ Task Assignment         │  │
│  │ - Queue management      │  │
│  │ - Parallel execution     │  │
│  └───────────┬──────────────┘  │
│              │                 │
│  ┌───────────▼──────────────┐  │
│  │ Execution Monitoring     │  │
│  │ - Progress tracking     │  │
│  │ - Error handling        │  │
│  │ - Performance metrics   │  │
│  └───────────┬──────────────┘  │
└──────────────┼──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Result Aggregation             │
└─────────────────────────────────┘
```

## Storage Architecture

### File Structure

```
JARVIS/
├── History/                    # Data storage
│   ├── JARVISConversation_history.txt
│   ├── chat.txt
│   ├── memory.txt
│   ├── rag_storage/
│   │   ├── documents.json
│   │   ├── embeddings.npy
│   │   └── index.json
│   └── function_call_history.txt
├── tool_usage.json            # Dataset storage
├── config/
│   └── config.py
└── requirements.txt
```

### Data Persistence

**Conversation Data:**
- Real-time chat buffer (`chat.txt`)
- Full conversation history (`JARVISConversation_history.txt`)
- Memory summaries (`memory.txt`)

**RAG Data:**
- Document storage (`documents.json`)
- Embedding cache (`embeddings.npy`)
- Keyword index (`index.json`)

**Dataset Data:**
- Tool usage logs (`tool_usage.json`)
- Export formats (CSV, Parquet, etc.)

## Integration Points

### External APIs

1. **Webscout Provider**
   - C4ai for text generation
   - TextPollinationsAI for function calling
   - WEBS for web search

2. **Embedding Services**
   - sentence-transformers (local)
   - OpenAI embeddings (cloud)

3. **Web Services**
   - Felo AI (research search)
   - Speedtest.net (internet speed)
   - News APIs

### Internal Integrations

```
┌─────────────────────────────────────────────────────────┐
│                  Integration Matrix                     │
├───────────────────┬─────────────────────────────────────┤
│ Component          │ Integrates With                     │
├───────────────────┼─────────────────────────────────────┤
│ main.py           │ All subsystems                      │
│ conversation/     │ RAG, Dataset, Config                 │
│ rag_system.py     │ conversation/, embeddings            │
│ AGENTS/          │ TOOL/, webscout, conversation/        │
│ TOOL/             │ RESEARCH/felo, external APIs        │
│ dataset.py        │ main.py, conversation/               │
│ config/           │ All subsystems                      │
│ jprinter/         │ AGENTS/, debugging                   │
└───────────────────┴─────────────────────────────────────┘
```

## Performance Considerations

### Optimization Strategies

1. **Caching**
   - Embedding cache for repeated queries
   - Document index caching
   - Conversation history caching

2. **Async Operations**
   - Parallel agent execution
   - Async tool calls
   - Background summarization

3. **Memory Management**
   - Automatic history trimming
   - Memory cleanup based on importance
   - Token limit optimization

4. **Error Handling**
   - Retry logic with exponential backoff
   - Graceful degradation
   - Fallback mechanisms

## Security Considerations

1. **API Keys**
   - Environment variable storage
   - .env file support
   - No hardcoded credentials

2. **Data Privacy**
   - Local-first approach
   - Optional cloud embeddings
   - User-controlled data retention

3. **Input Validation**
   - URL validation for web tools
   - File path sanitization
   - Query parameter checking

## Future Extension Points

1. **New Tools**
   - Add to `TOOL/` directory
   - Register with `@tools` decorator
   - Update tool descriptions

2. **New Agents**
   - Extend `BaseAgent` class
   - Register with `AgentCoordinator`
   - Define capabilities

3. **New Embedding Backends**
   - Extend embedding backend enum
   - Implement backend class
   - Add to `EmbeddingManager`

4. **New Retrieval Strategies**
   - Extend retriever classes
   - Add to `HybridRetriever`
   - Implement custom scoring

## Dependencies

### Core Dependencies
- `webscout` - Web search and AI provider
- `sentence-transformers` - Local embeddings
- `rich` - Console formatting
- `requests` - HTTP requests
- `PyPDF2` - PDF processing
- `html2text` - HTML to text conversion
- `speedtest-cli` - Internet speed testing

### Data Processing
- `pandas` - Data manipulation
- `pyarrow` - Parquet support
- `datasets` - HuggingFace datasets

### Utilities
- `colorama` - Terminal colors
- `pygments` - Syntax highlighting
- `executing` - Source code analysis
- `python-dotenv` - Environment variables
- `beautifulsoup4` - HTML parsing

## Conclusion

JARVIS represents a sophisticated agentic AI system with modular architecture designed for extensibility and maintainability. The system leverages modern AI techniques including RAG, multi-agent coordination, and semantic memory to provide intelligent, context-aware assistance.

The architecture supports:
- **Scalability**: Modular design allows easy addition of new components
- **Flexibility**: Multiple embedding backends and retrieval strategies
- **Reliability**: Comprehensive error handling and fallback mechanisms
- **Performance**: Caching, async operations, and optimization strategies
- **Extensibility**: Clear extension points for new tools, agents, and capabilities

This architecture serves as a solid foundation for building advanced AI assistants with agentic capabilities.
