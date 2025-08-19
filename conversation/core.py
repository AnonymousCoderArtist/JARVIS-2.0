"""
Enhanced JARVIS Conversation System - Core Implementation
"""
import logging
import os
import threading
import time
import uuid
from typing import List, Dict, Any, Optional

from .config import ConversationConfig, EmbeddingConfig, EmbeddingBackend
from .embeddings import EmbeddingManager
from .memory import MemoryManager
from .prompt_optimizer import PromptOptimizer


class JARVISConversation:
    """Enhanced conversation management system with embedding support and improved memory"""
    
    def __init__(
        self,
        name: str = "Vortex",
        status: bool = True,
        config: Optional[ConversationConfig] = None,
        embedding_config: Optional[EmbeddingConfig] = None
    ):
        # Configuration setup
        self.name = name
        self.status = status
        self.config = config or ConversationConfig()
        
        # Update embedding config if provided
        if embedding_config:
            self.config.embedding = embedding_config
        
        # Initialize file paths
        self._ensure_directories()
        
        # Initialize components
        self.embedding_manager = self._initialize_embedding_manager()
        self.memory_manager = MemoryManager(self.config, self.embedding_manager)
        self.prompt_optimizer = PromptOptimizer(self.config, self.memory_manager)
        
        # Conversation state
        self.intro = self.prompt_optimizer.generate_intro_prompt(name)
        self.chat_history = ""
        self.history_format = "\\n%(role)s: %(content)s"
        
        # Chat buffer for periodic summarization
        self.chat_buffer: List[str] = []
        self.last_save_time = time.time()
        
        # Load existing conversation
        self._load_conversation_history()
        
        # Start background processes
        self._start_background_processes()
    
    def _ensure_directories(self) -> None:
        """Ensure all necessary directories exist"""
        os.makedirs(self.config.history_folder, exist_ok=True)
    
    def _initialize_embedding_manager(self) -> Optional[EmbeddingManager]:
        """Initialize embedding manager based on configuration"""
        if self.config.embedding.backend == EmbeddingBackend.NONE:
            return None
        
        embeddings_path = self.config.get_file_path(self.config.embeddings_file)
        try:
            return EmbeddingManager(self.config.embedding, embeddings_path)
        except Exception as e:
            logging.error(f"Failed to initialize embedding manager: {e}")
            return None
    
    def _start_background_processes(self) -> None:
        """Start background threads for memory management"""
        self.summarization_thread = threading.Thread(
            target=self._periodic_memory_summary,
            daemon=True
        )
        self.summarization_thread.start()
    
    def add_message(self, role: str, content: str, importance: float = 0.5) -> str:
        """Add a message to the conversation with optional importance scoring"""
        message_id = str(uuid.uuid4())
        formatted_message = self.history_format % {"role": role, "content": content}
        
        # Update conversation history
        self.chat_history += formatted_message
        self.chat_buffer.append(formatted_message)
        
        # Save to files
        self._save_to_files(formatted_message)
        
        # Add to embeddings if available
        if self.embedding_manager:
            self.embedding_manager.add_text(
                text_id=message_id,
                text=content,
                metadata={
                    "role": role,
                    "timestamp": time.time(),
                    "importance": importance,
                    "type": "conversation"
                }
            )
        
        return message_id
    
    def generate_complete_prompt(self, user_input: str, include_memories: bool = True) -> str:
        """Generate a complete prompt with context, history, and memories"""
        if not self.status:
            return user_input
        
        # Get optimized prompt with context
        complete_prompt = self.prompt_optimizer.optimize_prompt_for_context(
            base_prompt=self.intro,
            conversation_history=self.chat_history,
            user_input=user_input
        )
        
        return complete_prompt
    
    def generate_tool_response_prompt(self, user_input: str, tool_outputs: List[Dict[str, Any]]) -> str:
        """Generate prompt for AI response based on tool outputs"""
        base_prompt = self.prompt_optimizer.enhance_tool_response_prompt(user_input, tool_outputs)
        
        # Add conversation context
        return self.prompt_optimizer.optimize_prompt_for_context(
            base_prompt=self.intro + "\\n" + base_prompt,
            conversation_history=self.chat_history,
            user_input=user_input
        )
    
    def process_interaction(self, user_input: str, ai_response: str, 
                          tool_outputs: Optional[List[Dict[str, Any]]] = None) -> None:
        """Process a complete interaction (user input + AI response + tools)"""
        tool_outputs = tool_outputs or []
        
        # Add messages to conversation
        self.add_message("User", user_input, importance=0.6)
        self.add_message("JARVIS", ai_response, importance=0.7)
        
        # Add tool outputs as separate messages
        for tool_output in tool_outputs:
            tool_name = tool_output.get('name', 'Unknown')
            output_summary = str(tool_output.get('output', ''))[:200] + "..." if len(str(tool_output.get('output', ''))) > 200 else str(tool_output.get('output', ''))
            self.add_message(f"Tool_{tool_name}", output_summary, importance=0.8)
        
        # Create memory if worthy
        memory_content = self.prompt_optimizer.create_memory_worthy_content(
            user_input, ai_response, tool_outputs
        )
        
        if memory_content:
            self.memory_manager.add_memory(
                content=memory_content,
                metadata={
                    "interaction_type": "tool_usage" if tool_outputs else "conversation",
                    "tools_used": [t.get('name') for t in tool_outputs],
                    "user_input": user_input[:100]
                },
                importance=0.8 if tool_outputs else 0.6
            )
    
    def search_conversation_history(self, query: str, max_results: int = 5) -> List[str]:
        """Search conversation history using embeddings or keyword matching"""
        if self.embedding_manager:
            results = self.embedding_manager.search_similar(query, max_results)
            return [result[2] for result in results]  # Extract text content
        else:
            # Fallback to simple keyword search
            return self._keyword_search_history(query, max_results)
    
    def _keyword_search_history(self, query: str, max_results: int) -> List[str]:
        """Simple keyword search in conversation history"""
        query_words = query.lower().split()
        lines = self.chat_history.split('\\n')
        matches = []
        
        for line in lines:
            if any(word in line.lower() for word in query_words):
                matches.append(line.strip())
                if len(matches) >= max_results:
                    break
        
        return matches
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation state"""
        memory_stats = self.memory_manager.get_stats()
        embedding_stats = self.embedding_manager.get_stats() if self.embedding_manager else {}
        
        return {
            "user_name": self.name,
            "conversation_length": len(self.chat_history),
            "messages_in_buffer": len(self.chat_buffer),
            "memory_stats": memory_stats,
            "embedding_stats": embedding_stats,
            "last_save_time": self.last_save_time,
            "status": self.status
        }
    
    def clear_conversation(self, keep_memories: bool = True) -> None:
        """Clear conversation history, optionally keeping memories"""
        self.chat_history = ""
        self.chat_buffer = []
        
        # Clear history files
        for filename in [self.config.conversation_file, self.config.chat_file]:
            filepath = self.config.get_file_path(filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Clear memories if requested
        if not keep_memories:
            self.memory_manager.clear_memories()
        
        # Clear embeddings for conversation (keep memory embeddings)
        if self.embedding_manager and not keep_memories:
            self.embedding_manager.clear_embeddings()
    
    def export_conversation(self, format: str = "json") -> str:
        """Export conversation in specified format"""
        import json
        from datetime import datetime
        
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "user_name": self.name,
            "conversation_history": self.chat_history,
            "memories": [memory.to_dict() for memory in self.memory_manager.memories],
            "stats": self.get_conversation_summary()
        }
        
        if format.lower() == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif format.lower() == "txt":
            return f"""
JARVIS Conversation Export
User: {self.name}
Export Date: {data['export_timestamp']}

=== CONVERSATION HISTORY ===
{self.chat_history}

=== MEMORIES ===
{chr(10).join([memory['content'] for memory in data['memories']])}
"""
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _load_conversation_history(self) -> None:
        """Load existing conversation history from file"""
        conversation_file = self.config.get_file_path(self.config.conversation_file)
        
        if os.path.exists(conversation_file):
            try:
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content and not content.startswith('<system_context>'):
                        self.chat_history = content
            except Exception as e:
                logging.error(f"Failed to load conversation history: {e}")
    
    def _save_to_files(self, message: str) -> None:
        """Save message to conversation files"""
        # Save to main conversation file
        conversation_file = self.config.get_file_path(self.config.conversation_file)
        try:
            with open(conversation_file, 'a', encoding='utf-8') as f:
                f.write(message + '\\n')
        except Exception as e:
            logging.error(f"Failed to save to conversation file: {e}")
        
        # Save to chat file (real-time)
        chat_file = self.config.get_file_path(self.config.chat_file)
        try:
            with open(chat_file, 'a', encoding='utf-8') as f:
                f.write(message + '\\n')
        except Exception as e:
            logging.error(f"Failed to save to chat file: {e}")
    
    def _periodic_memory_summary(self) -> None:
        """Periodically process chat buffer and create memory summaries"""
        while True:
            time.sleep(self.config.save_interval)
            current_time = time.time()
            
            if (current_time - self.last_save_time >= self.config.save_interval and 
                len(self.chat_buffer) > 0):
                
                self.last_save_time = current_time
                
                # Create summary of recent interactions
                if len(self.chat_buffer) >= 4:  # At least 2 exchanges
                    chat_summary = self._summarize_chat_buffer()
                    if chat_summary:
                        self.memory_manager.add_memory(
                            content=chat_summary,
                            metadata={
                                "type": "periodic_summary",
                                "message_count": len(self.chat_buffer)
                            },
                            importance=0.5
                        )
                
                # Clear buffer
                self.chat_buffer = []
    
    def _summarize_chat_buffer(self) -> str:
        """Create a summary of the current chat buffer"""
        if not self.chat_buffer:
            return ""
        
        # Simple extraction of key topics and actions
        buffer_text = "\\n".join(self.chat_buffer)
        
        # Look for questions, tools used, and key information
        summary_parts = []
        
        # Extract user questions
        user_messages = [msg for msg in self.chat_buffer if msg.strip().startswith("User:")]
        if user_messages:
            last_question = user_messages[-1].replace("User:", "").strip()
            summary_parts.append(f"User inquired about: {last_question[:100]}")
        
        # Extract tool usage
        tool_messages = [msg for msg in self.chat_buffer if "Tool_" in msg]
        if tool_messages:
            tools_used = list(set([msg.split(":")[0].replace("\\n", "").replace("Tool_", "") for msg in tool_messages]))
            summary_parts.append(f"Tools used: {', '.join(tools_used)}")
        
        # Extract JARVIS responses with key information
        jarvis_messages = [msg for msg in self.chat_buffer if msg.strip().startswith("JARVIS:")]
        if jarvis_messages:
            last_response = jarvis_messages[-1].replace("JARVIS:", "").strip()[:100]
            summary_parts.append(f"JARVIS provided: {last_response}")
        
        return " | ".join(summary_parts) if summary_parts else "General conversation"