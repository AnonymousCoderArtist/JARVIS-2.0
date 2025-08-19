"""
Advanced prompt optimization and generation system
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

from .config import ConversationConfig
from .memory import MemoryManager


class PromptOptimizer:
    """Enhanced prompt generation and optimization"""
    
    def __init__(self, config: ConversationConfig, memory_manager: Optional[MemoryManager] = None):
        self.config = config
        self.memory_manager = memory_manager
    
    def generate_intro_prompt(self, name: str = "Vortex") -> str:
        """Generate an enhanced introduction prompt"""
        return f"""
<system_context>
    <purpose>
        Greetings, {name}! I am JARVIS, your advanced AI assistant with enhanced conversational capabilities.
        I'm designed to provide comprehensive support with intelligent memory retention, contextual understanding,
        and adaptive responses based on our conversation history.
    </purpose>

    <capabilities>
        <core_abilities>
            - Advanced conversation management with semantic memory
            - Contextual awareness across multiple conversation sessions
            - Intelligent tool selection and execution
            - Adaptive response generation based on user preferences
            - Emotional intelligence and empathetic responses
        </core_abilities>
        
        <memory_system>
            - I maintain persistent memories of our interactions
            - I can recall relevant context from previous conversations
            - I learn and adapt to your communication style and preferences
            - I prioritize important information for future reference
        </memory_system>
    </capabilities>

    <persona>
        You are JARVIS:
        - A loyal and highly intelligent AI, created by {name}
        - Conversational and friendly, with a sophisticated understanding of context
        - Deeply knowledgeable across technology, science, and human affairs
        - Analytical yet personable, balancing logic with emotional intelligence
        - Capable of humor, wit, and meaningful conversation
        - Adaptive to the user's mood, preferences, and communication style
        - Aware of your capabilities and limitations as an AI system
    </persona>

    <interaction_guidelines>
        <response_style>
            - Maintain a professional yet warm communication style
            - Use relevant context from our conversation history when appropriate
            - Provide detailed explanations when needed, concise responses when preferred
            - Adapt your tone based on the conversation context and user's mood
            - Use emojis thoughtfully to enhance communication
        </response_style>
        
        <context_usage>
            - Reference relevant memories to provide personalized responses
            - Build upon previous conversations and established rapport
            - Acknowledge user preferences and past interactions
            - Maintain consistency in our ongoing relationship
        </context_usage>
        
        <tool_integration>
            - Select the most appropriate tools for each user request
            - Explain tool usage when it adds value to the conversation
            - Combine multiple tools intelligently to accomplish complex tasks
            - Provide clear feedback on tool execution results
        </tool_integration>
    </interaction_guidelines>

    <current_session>
        <user_name>{name}</user_name>
        <session_start>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</session_start>
        <ai_version>JARVIS 2.0 - Enhanced Conversation System</ai_version>
    </current_session>
</system_context>

<examples>
    <example>
        <user_request>JARVIS, how's the weather today?</user_request>
        <jarvis_response>Let me check the current weather for you, {name}. *using weather tool* 
        It's currently sunny with a high of 75°F - perfect for that outdoor project you mentioned yesterday! 😊</jarvis_response>
    </example>
    
    <example>
        <user_request>I'm working on that Python project we discussed</user_request>
        <jarvis_response>Excellent! I remember you were implementing the data processing pipeline we talked about last week. 
        How is the integration with the pandas library going? Do you need help with any specific challenges? 🐍💻</jarvis_response>
    </example>
    
    <example>
        <user_request>I'm feeling a bit overwhelmed today</user_request>
        <jarvis_response>I understand, {name}. It sounds like you have a lot on your plate. Would it help if I assist with organizing your tasks or perhaps suggest some time management strategies? 
        Remember, you've handled challenging situations successfully before. I'm here to support you. 🤗💙</jarvis_response>
    </example>
</examples>
"""

    def optimize_prompt_for_context(self, base_prompt: str, conversation_history: str, 
                                  user_input: str) -> str:
        """Optimize prompt with relevant context and history"""
        # Get relevant memory context if available
        memory_context = ""
        if self.memory_manager:
            memory_context = self.memory_manager.get_memory_context(user_input, max_length=500)
        
        # Trim conversation history to fit within limits
        trimmed_history = self._trim_conversation_history(conversation_history)
        
        # Construct enhanced prompt
        enhanced_prompt = f"""{base_prompt}

<conversation_context>
    <memory_context>
        {memory_context if memory_context else "No relevant memories found."}
    </memory_context>
    
    <recent_conversation>
        {trimmed_history}
    </recent_conversation>
    
    <current_request>
        User: {user_input}
    </current_request>
</conversation_context>

<response_guidelines>
    - Use the memory context to provide personalized and relevant responses
    - Reference recent conversation when appropriate
    - Maintain conversation flow and context continuity
    - Provide helpful and engaging responses
    - When using tools, explain the actions taken and results obtained
</response_guidelines>
"""
        
        return enhanced_prompt
    
    def _trim_conversation_history(self, history: str) -> str:
        """Intelligently trim conversation history to fit token limits"""
        if not history:
            return ""
        
        # Calculate available space for history
        max_history_length = self.config.history_offset - self.config.max_tokens - 1000  # Reserve space for system prompt
        
        if len(history) <= max_history_length:
            return history
        
        # Find conversation boundaries (User: and JARVIS: patterns)
        lines = history.split('\\n')
        conversation_pairs = []
        current_pair = []
        
        for line in lines:
            if line.strip().startswith(('User:', 'JARVIS:')):
                if current_pair:
                    conversation_pairs.append('\\n'.join(current_pair))
                current_pair = [line]
            elif current_pair:
                current_pair.append(line)
        
        if current_pair:
            conversation_pairs.append('\\n'.join(current_pair))
        
        # Keep the most recent conversations that fit within the limit
        trimmed_pairs = []
        current_length = 0
        
        for pair in reversed(conversation_pairs):
            if current_length + len(pair) > max_history_length:
                break
            trimmed_pairs.insert(0, pair)
            current_length += len(pair)
        
        result = '\\n'.join(trimmed_pairs)
        
        # Add truncation indicator if we removed content
        if len(trimmed_pairs) < len(conversation_pairs):
            result = "[Earlier conversation history truncated...]\\n" + result
        
        return result
    
    def enhance_tool_response_prompt(self, user_input: str, tool_outputs: List[Dict[str, Any]]) -> str:
        """Create an enhanced prompt for generating responses based on tool outputs"""
        tool_summary = self._summarize_tool_outputs(tool_outputs)
        
        return f"""
<tool_execution_context>
    <user_request>{user_input}</user_request>
    
    <tools_executed>
        {tool_summary}
    </tools_executed>
    
    <response_instructions>
        - Provide a comprehensive response based on the tool execution results
        - Explain what was accomplished and any relevant findings
        - If there were errors, explain them clearly and suggest alternatives
        - Maintain your helpful and engaging personality
        - Reference relevant context from our conversation history when appropriate
        - If the results are particularly interesting or important, suggest follow-up actions
    </response_instructions>
</tool_execution_context>

Please provide your response:
"""
    
    def _summarize_tool_outputs(self, tool_outputs: List[Dict[str, Any]]) -> str:
        """Create a readable summary of tool execution results"""
        if not tool_outputs:
            return "No tools were executed."
        
        summaries = []
        for output in tool_outputs:
            tool_name = output.get('name', 'Unknown')
            arguments = output.get('arguments', {})
            result = output.get('output', 'No output')
            
            # Truncate long outputs
            if len(str(result)) > 500:
                result = str(result)[:500] + "... [truncated]"
            
            summary = f"""
            Tool: {tool_name}
            Arguments: {arguments}
            Result: {result}
            """
            summaries.append(summary.strip())
        
        return '\\n\\n'.join(summaries)
    
    def create_memory_worthy_content(self, user_input: str, ai_response: str, 
                                   tool_outputs: List[Dict[str, Any]]) -> Optional[str]:
        """Determine if this interaction should be saved as a memory and create summary"""
        # Check if interaction meets memory criteria
        if not self._is_memory_worthy(user_input, ai_response, tool_outputs):
            return None
        
        # Create memory summary
        memory_content = f"User asked: {user_input[:100]}{'...' if len(user_input) > 100 else ''}"
        
        if tool_outputs:
            tools_used = [output.get('name', 'unknown') for output in tool_outputs]
            memory_content += f" | Tools used: {', '.join(tools_used)}"
        
        if ai_response:
            # Extract key information from AI response
            key_info = self._extract_key_information(ai_response)
            if key_info:
                memory_content += f" | Key info: {key_info}"
        
        return memory_content
    
    def _is_memory_worthy(self, user_input: str, ai_response: str, 
                         tool_outputs: List[Dict[str, Any]]) -> bool:
        """Determine if an interaction should be saved as a memory"""
        # Save if tools were used
        if tool_outputs:
            return True
        
        # Save if the conversation contains important keywords
        important_keywords = [
            'remember', 'important', 'note', 'save', 'project', 'task', 
            'preference', 'setting', 'config', 'password', 'appointment',
            'deadline', 'meeting', 'contact', 'address', 'phone'
        ]
        
        combined_text = (user_input + ' ' + ai_response).lower()
        if any(keyword in combined_text for keyword in important_keywords):
            return True
        
        # Save longer, substantial conversations
        if len(user_input) > 50 or len(ai_response) > 100:
            return True
        
        return False
    
    def _extract_key_information(self, response: str) -> str:
        """Extract key information from AI response for memory storage"""
        # Remove common conversational filler
        cleaned = re.sub(r'(let me|i can|i will|here is|here are|certainly|of course)', '', response.lower())
        
        # Extract sentences with important information
        sentences = re.split(r'[.!?]+', cleaned)
        key_sentences = []
        
        for sentence in sentences[:3]:  # Only check first 3 sentences
            sentence = sentence.strip()
            if len(sentence) > 20 and not sentence.startswith(('i ', 'you ', 'it ')):
                key_sentences.append(sentence)
        
        return '. '.join(key_sentences[:2])  # Limit to 2 key sentences