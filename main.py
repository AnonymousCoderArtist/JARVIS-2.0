import subprocess
from typing import List, Dict, Any
from webscout.Provider import *
from AGENTS.functioncall import FunctionCallingAgent, Fn
from AGENTS.coordinator import EnhancedJARVIS, TaskPriority
import inspect
from rich import print as rprint
from dataset import DatasetBuilder
from conversation import JARVISConversation
from conversation.config import ConversationConfig, EmbeddingConfig, EmbeddingBackend
from TOOL.main import ask_website, check_internet_speed, get_news, process_pdf, websearch # Import the tools
from config.config import Config
from rag_system import RAGSystem, RAGConfig, enhance_conversation_with_rag

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

functions: List[Fn] = []
local_vars: Dict[str, Any] = locals().copy() #Copy the local vars
for name, obj in local_vars.items():
    if callable(obj) and hasattr(obj, '_is_tool'):
        sig = inspect.signature(obj)
        parameters = {param.name: "string" if param.annotation is inspect._empty else str(param.annotation).replace("<class '","").replace("'>","") for param in sig.parameters.values()}
        
        docstring = obj.__doc__ if obj.__doc__ else " "
        
        functions.append(Fn(name=name, description=docstring, parameters=parameters))

class JARVIS:
    def __init__(self):
        self.dataset_builder = DatasetBuilder(filepath=Config.DATASET_FILE)  # Initialize DatasetBuilder
        
        # Initialize enhanced conversation system
        conversation_config = ConversationConfig()
        # You can configure embedding backend here:
        # conversation_config.embedding = EmbeddingConfig(
        #     backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,  # or EmbeddingBackend.OPENAI or EmbeddingBackend.NONE
        #     model_name="all-MiniLM-L6-v2",  # for sentence-transformers
        #     api_key="your-openai-api-key"  # for OpenAI
        # )
        
        self.conversation = JARVISConversation(config=conversation_config)  # Initialize enhanced conversation
        
        # Initialize RAG system and enhance conversation
        rag_config = RAGConfig(
            embedding_backend="sentence_transformers",
            enable_semantic_search=True,
            enable_keyword_search=True,
            max_retrieval_results=5
        )
        self.rag_system = RAGSystem(rag_config)
        enhance_conversation_with_rag(self.conversation, rag_config)
        
        # Initialize enhanced agent coordination system
        self.enhanced_jarvis = EnhancedJARVIS()
        
        self.agent = FunctionCallingAgent(tools=functions) #pass the list of tools to the agent class
        self.ai = C4ai(
            is_conversation=False,
            system_prompt=self.conversation.intro
        )
        
        rprint("[bold green]🤖 JARVIS Enhanced System Initialized[/]")
        rprint("[bold blue]✅ Advanced Conversation System with Memory[/]")
        rprint("[bold blue]✅ RAG (Retrieval Augmented Generation) System[/]")
        rprint("[bold blue]✅ Multi-Agent Coordination Framework[/]")
        rprint("[bold blue]✅ Enhanced Tool Integration[/]")
        print()

    def process_with_rag(self, user_input: str) -> str:
        """Process user input with RAG enhancement."""
        # Generate RAG-enhanced prompt
        enhanced_prompt = self.rag_system.generate_context_prompt(user_input)
        
        # Add conversation memory to RAG
        if hasattr(self.conversation, 'memory_manager'):
            recent_memories = self.conversation.memory_manager.search_memories(user_input, limit=3)
            if recent_memories:
                memory_context = "\n".join([
                    f"Memory: {memory['content'][:200]}..." 
                    for memory in recent_memories
                ])
                enhanced_prompt = f"{enhanced_prompt}\n\nRelevant Memory Context:\n{memory_context}"
        
        return enhanced_prompt


    def execute_tool_and_respond(self, user_input: str) -> None:
        """
        Executes a tool based on user input using the FunctionCallingAgent and provides a response.
        Enhanced with RAG and agent coordination.
        """
        try:
            # Process with RAG enhancement first
            rag_enhanced_input = self.process_with_rag(user_input)
            
            # Check if this should be handled by the agent coordination system
            if any(keyword in user_input.lower() for keyword in [
                "complex", "multi-step", "plan", "coordinate", "analyze and", "research and"
            ]):
                rprint("[bold cyan]🤖 Using Enhanced Agent System[/]")
                
                # Determine priority
                priority = TaskPriority.HIGH if any(urgent in user_input.lower() for urgent in ["urgent", "quickly", "asap"]) else TaskPriority.NORMAL
                
                # Process with enhanced agent system
                agent_result = self.enhanced_jarvis.process_request(user_input, priority)
                
                if agent_result["error"]:
                    error_message = f"Agent system error: {agent_result['error']}"
                    rprint(f"[bold red]JARVIS:[/] {error_message}")
                    self.conversation.add_message("JARVIS", error_message, importance=0.3)
                    return
                
                # Generate response based on agent result
                if agent_result["result"]:
                    ai_prompt = f"""Based on the following analysis and results, provide a comprehensive response to the user:

User Request: {user_input}
Agent Analysis Result: {agent_result['result']}

Please synthesize this information into a helpful, conversational response."""
                    
                    llm_response = "".join(self.ai.chat(ai_prompt))
                    rprint(f"[bold green]JARVIS:[/] {llm_response}")
                    
                    # Add to conversation and RAG
                    self.conversation.add_message("User", user_input, importance=0.8)
                    self.conversation.add_message("JARVIS", llm_response, importance=0.8)
                    self.rag_system.add_conversation_memory(user_input, llm_response)
                    
                    return
            
            # Get enhanced prompt with conversation context
            enhanced_prompt = self.conversation.generate_complete_prompt(rag_enhanced_input)
            
            function_call_data = self.agent.function_call_handler(enhanced_prompt)
            
            if "error" in function_call_data:
                error_message = f"I've encountered an error: {function_call_data['error']}"
                rprint(f"[bold red]JARVIS:[/] {error_message}")
                self.conversation.add_message("JARVIS", error_message, importance=0.3)
                return
            
            tool_calls = function_call_data.get("tool_calls", [])
            tool_outputs = []
            
            for tool_call in tool_calls:
                function_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})
                
                if not function_name:
                    rprint("[bold red]JARVIS: Tool name not found in the tool call data.[/]")
                    return
                
                if hasattr(self, function_name):
                    try:
                         function_to_call = getattr(self, function_name)
                         tool_output = function_to_call(**arguments) # Execute the function
                         tool_outputs.append({"name": function_name, "output": tool_output, "arguments": arguments})
                         rprint(f"[bold blue]Tool:[/] Executed tool '{function_name}'")
                         
                    except Exception as e:
                        rprint(f"[bold red]JARVIS:[/] Error executing tool '{function_name}': {e}")
                        tool_outputs.append({"name": function_name, "output": f"Error: {e}", "arguments": arguments})
                else:
                    rprint(f"[bold red]JARVIS:[/] Tool '{function_name}' not found in JARVIS class.")
                    tool_outputs.append({"name": function_name, "output": f"Tool not found", "arguments": arguments})
                    
            # Generate enhanced response using the improved conversation system
            if tool_outputs:
                ai_prompt = self.conversation.generate_tool_response_prompt(user_input, tool_outputs)
                llm_response = "".join(self.ai.chat(ai_prompt))
                rprint(f"[bold green]JARVIS:[/] {llm_response}")
                
                # Process the complete interaction for memory and context
                self.conversation.process_interaction(user_input, llm_response, tool_outputs)
                
                # Add to RAG system for future retrieval
                self.rag_system.add_conversation_memory(user_input, llm_response, {
                    "tools_used": [tool["name"] for tool in tool_outputs],
                    "importance": 0.8 if tool_outputs else 0.5
                })

                # Add datapoint to the dataset
                self.dataset_builder.add_datapoint(
                    user_input=user_input,
                    tool_calls=tool_outputs,
                    response=llm_response
                )
            else:
               error_msg = "No valid tool outputs to construct an AI response."
               rprint(f"[bold red]JARVIS: {error_msg}[/]")
               self.conversation.add_message("JARVIS", error_msg, importance=0.3)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            rprint(f"[bold red]{error_msg}[/]")
            self.conversation.add_message("JARVIS", error_msg, importance=0.3)
    
    def show_system_status(self):
        """Display comprehensive system status."""
        rprint("\n[bold cyan]🤖 JARVIS Enhanced System Status[/]")
        rprint("=" * 50)
        
        # Conversation system stats
        conv_stats = self.conversation.get_stats() if hasattr(self.conversation, 'get_stats') else {}
        rprint(f"[bold blue]💬 Conversation System:[/]")
        rprint(f"  Messages: {conv_stats.get('total_messages', 'N/A')}")
        rprint(f"  Memory Entries: {conv_stats.get('memory_count', 'N/A')}")
        
        # RAG system stats
        rag_stats = self.rag_system.get_stats()
        rprint(f"[bold blue]🧠 RAG System:[/]")
        rprint(f"  Documents: {rag_stats.get('total_documents', 0)}")
        rprint(f"  Embeddings: {rag_stats.get('documents_with_embeddings', 0)}")
        rprint(f"  Conversations: {rag_stats.get('conversation_documents', 0)}")
        
        # Agent system stats
        agent_stats = self.enhanced_jarvis.get_status()
        rprint(f"[bold blue]🤝 Agent Coordination:[/]")
        rprint(f"  Active Agents: {len(agent_stats['coordinator_status']['agents'])}")
        rprint(f"  Completed Tasks: {agent_stats['coordinator_status']['tasks']['completed']}")
        rprint(f"  Success Rate: {agent_stats['coordinator_status']['performance']['success_rate']:.2%}")
        
        print()
    
    def export_all_data(self, format_type: str = "json") -> Dict[str, str]:
        """Export all system data."""
        exports = {}
        
        # Export conversation data
        if hasattr(self.conversation, 'export_conversation'):
            exports['conversation'] = self.conversation.export_conversation(format_type)
        
        # Export RAG data
        exports['rag_system'] = self.rag_system.export_data(format_type)
        
        # Export agent system status
        exports['agent_system'] = self.enhanced_jarvis.get_status()
        
        return exports
########################################
# Tool Wrappers
########################################
    def ask_website(self, url: str, **kwargs) -> str:
        """Wrapper for ask_website tool with error handling."""
        try:
            # Pass the URL as positional argument and everything else as keyword arguments
            return ask_website(url, **kwargs)
        except Exception as e:
            rprint(f"[bold red]JARVIS:[/] Error using ask_website: {e}")
            return f"Error using ask_website: {e}"

    def check_internet_speed(self) -> str:
         """Wrapper for check_internet_speed tool with error handling."""
         try:
            return check_internet_speed()
         except Exception as e:
            rprint(f"[bold red]JARVIS:[/] Error using check_internet_speed: {e}")
            return f"Error using check_internet_speed: {e}"

    def get_news(self, topic: str, max_results: int = 3) -> str:
         """Wrapper for get_news tool with error handling."""
         try:
            return get_news(topic, max_results)
         except Exception as e:
            rprint(f"[bold red]JARVIS:[/] Error using get_news: {e}")
            return f"Error using get_news: {e}"
    
    def websearch(self, query: str, timeout: int = 30, stream: bool = False) -> str:
         """Wrapper for websearch tool with error handling."""
         try:
            return websearch(query, timeout, stream)
         except Exception as e:
            rprint(f"[bold red]JARVIS:[/] Error using websearch: {e}")
            return f"Error using websearch: {e}"
         
    def process_pdf(self, input_path: str, output_mode: str = 'both', output_path: str = None, show_page_breaks: bool = True) -> str:
          """Wrapper for the process_pdf tool with error handling."""
          try:
             return process_pdf(input_path, output_mode, output_path, show_page_breaks)
          except Exception as e:
              rprint(f"[bold red]JARVIS:[/] Error using process_pdf: {e}")
              return f"Error using process_pdf: {e}"
              
    def general_ai(self, question: str) -> str:
        return question
######################################################
# Main function to run the JARVIS assistant          #
######################################################
def main():
    jarvis = JARVIS()
    try:
        while True:
            user_input = input(">>> ").strip()
            if user_input.lower() in ["exit", "quit", "bye"]:
                rprint("[bold green]JARVIS:[/] Exiting...")
                break
            elif user_input.lower() in ["status", "stats"]:
                jarvis.show_system_status()
                continue
            elif user_input.lower().startswith("export"):
                format_type = "json"
                if "txt" in user_input.lower():
                    format_type = "txt"
                exports = jarvis.export_all_data(format_type)
                rprint(f"[bold cyan]Exported data in {format_type} format[/]")
                continue
            if user_input:
                jarvis.execute_tool_and_respond(user_input)
    except KeyboardInterrupt:
        rprint("\n[bold green]JARVIS:[/] Exiting due to keyboard interrupt...")
    except Exception as e:
        rprint(f"[bold red]JARVIS:[/] An unexpected error occurred in main(): {e}")
    finally:
        # Clean shutdown
        if hasattr(jarvis, 'enhanced_jarvis'):
            jarvis.enhanced_jarvis.coordinator.shutdown()
        subprocess.run("clear")
        pass

if __name__ == "__main__":
    main()