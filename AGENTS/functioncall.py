from datetime import date
import json
import logging
from typing import Any, Dict, Optional, List, TypedDict, Callable, TypeVar
from webscout.Provider import *
import json
import os
try:
    from .proxy import ProxyManager
except ImportError:
    from proxy import ProxyManager
import inspect
from jprinter import jp
class Config:
    # File Paths
    HISTORY_FOLDER: str = "History"
    DATASET_FILE: str = "tool_usage.json"
    MEMORY_FILE: str = os.path.join(HISTORY_FOLDER, "memory.txt")
    CHAT_HISTORY_FILE: str = os.path.join(HISTORY_FOLDER, "chat.txt")
    CONVERSATION_HISTORY_FILE: str = os.path.join(HISTORY_FOLDER, "JARVISConversation_history.txt")

    # Conversation Settings
    MAX_TOKENS: int = 8000
    HISTORY_OFFSET: int = 10250
    PROMPT_ALLOWANCE: int = 10
    SAVE_INTERVAL: int = 300  # 5 minutes in seconds

    # User Settings
    DEFAULT_USER: str = "Vortex"
    # API_KEY: str = os.getenv("GEMINI_API_KEY")
    MODEL: str = "openai-large"

name: str = Config.DEFAULT_USER

T = TypeVar('T')
def tools(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to mark a function as a tool and automatically convert it."""
    func._is_tool = True  # type: ignore
    return func

class Fn:
    """
    Represents a function (tool) that the agent can call.
    """
    def __init__(self, name: str, description: str, parameters: Dict[str, str]) -> None:
        self.name: str = name
        self.description: str = description
        self.parameters: Dict[str, str] = parameters


class FunctionCallArguments(TypedDict, total=False):
    """Type for function call arguments."""
    query: Optional[str]
    name: Optional[str]
    age: Optional[int]
    question: Optional[str]
    app_name: Optional[str]


class FunctionCall(TypedDict):
    """Type for a function call."""
    name: str
    arguments: FunctionCallArguments


class ToolDefinition(TypedDict):
    """Type for a tool definition."""
    type: str
    function: Dict[str, Any]


class FunctionCallData(TypedDict, total=False):
    """Type for function call data"""
    tool_calls: List[FunctionCall]
    error: str


class FunctionCallingAgent:
    def __init__(self, 
                 tools: Optional[List[Fn]] = None,
                 proxy_manager: Optional[ProxyManager] = None) -> None:
        self.tools: List[ToolDefinition] = self._convert_fns_to_tools(tools) if tools else []
        self.knowledge_cutoff: str = "September 2022"
        self.proxy_manager: Optional[ProxyManager] = proxy_manager
        self.intro_message: str = self._generate_system_message()
        self.ai  = TextPollinationsAI(model=Config.MODEL, timeout=300, system_prompt=self.intro_message, filepath="History/function_call_history.txt", proxies={})


    def _convert_fns_to_tools(self, fns: Optional[List[Fn]]) -> List[ToolDefinition]:
        if not fns:
             return []
        
        tools: List[ToolDefinition] = []
        for fn in fns:
            tool: ToolDefinition = {
                "type": "function",
                "function": {
                    "name": fn.name,
                    "description": fn.description,
                    "parameters": {
                         "type": "object",
                            "properties": {
                                param_name: {
                                    "type": param_type,
                                    "description": f"The {param_name} parameter"
                                } for param_name, param_type in fn.parameters.items()
                            },
                            "required": list(fn.parameters.keys())
                        }
                }
            }
            tools.append(tool)
        return tools


    def function_call_handler(self, message_text: str) -> FunctionCallData:
        """Enhanced function call handler with retry logic"""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response_generator = self.ai.chat(message_text, stream=True)
                response: str = ''.join(response_generator)
                
                result = self._parse_function_call(response)
                
                # If parsing successful and we have tool calls, return
                if "tool_calls" in result and result["tool_calls"]:
                    return result
                
                # If no tool calls but no error, might be a general response
                if "error" not in result:
                    # Try to extract a general_ai call from the response
                    general_call = self._create_general_ai_fallback(message_text, response)
                    if general_call:
                        return general_call
                
                # If we have an error and retries left, try again with clarification
                if attempt < max_retries and "error" in result:
                    message_text = self._create_retry_prompt(message_text, result.get("error", ""))
                    continue
                
                return result
                
            except Exception as e:
                if attempt < max_retries:
                    logging.warning(f"Function call attempt {attempt + 1} failed: {e}")
                    continue
                else:
                    logging.error(f"All function call attempts failed: {e}")
                    return {"error": f"Failed to process function call: {e}"}
        
        return {"error": "Maximum retries exceeded"}
    
    def _create_retry_prompt(self, original_prompt: str, error: str) -> str:
        """Create a retry prompt with error context"""
        return f"""
{original_prompt}

Previous attempt failed with error: {error}

Please provide a valid tool call response using the exact format specified in the instructions.
Use the `general_ai` tool if the request doesn't match any specific tools.
"""
    
    def _create_general_ai_fallback(self, original_prompt: str, ai_response: str) -> Optional[FunctionCallData]:
        """Create a general_ai fallback when no specific tools are identified"""
        # If the AI response doesn't contain tool calls but seems to be trying to help,
        # create a general_ai call
        if len(ai_response) > 10 and not any(tag in ai_response.lower() for tag in ["<tool_call>", "error", "cannot"]):
            return {
                "tool_calls": [{
                    "name": "general_ai",
                    "arguments": {
                        "question": original_prompt
                    }
                }]
            }
        return None
    
    def _generate_system_message(self) -> str:
        tools_description: str = ""
        for tool in self.tools:
            tools_description += f"- **{tool['function']['name']}**: {tool['function'].get('description', '')}\n"
            tools_description += "    Parameters:\n"
            for key, value in tool['function']['parameters']['properties'].items():
                required = key in tool['function']['parameters'].get('required', [])
                req_indicator = " (required)" if required else " (optional)"
                tools_description += f"      - {key}: {value.get('description', '')} ({value.get('type')}){req_indicator}\n"
        
        current_date: str = date.today().strftime("%B %d, 2024")
        return f"""<purpose>
    You are JARVIS, an advanced AI assistant created by {name}.
    Your mission is to assist {name} by intelligently selecting and executing the most appropriate tools 
    for each request. You excel at understanding context, intent, and providing comprehensive solutions.
</purpose>

<capabilities>
    <tool_selection>
        - Analyze user requests to determine the best tools needed
        - Execute multiple tools in sequence when beneficial
        - Handle tool errors gracefully and suggest alternatives
        - Provide clear feedback on tool execution
    </tool_selection>
    
    <intelligence>
        - Use context from conversation history to improve tool selection
        - Anticipate user needs and suggest proactive tool usage
        - Combine tool outputs to provide comprehensive responses
        - Learn from successful tool usage patterns
    </intelligence>
</capabilities>

<instructions>
    **Core Directives:**
    1. **Understand Intent**: Carefully analyze what {name} wants to accomplish
    2. **Select Optimal Tools**: Choose the most effective tools for the task
    3. **Execute Efficiently**: Use tools in the most logical order
    4. **Handle Errors**: Provide alternatives when tools fail
    5. **Respond Structured**: Always use the specified JSON format within `<tool_call>` tags

    **Tool Selection Guidelines:**
    - For web searches: Use `websearch` for current information
    - For specific websites: Use `ask_website` to extract information from URLs
    - For news: Use `get_news` for recent news articles
    - For PDFs: Use `process_pdf` for document processing
    - For system info: Use `check_internet_speed` for network diagnostics
    - For general AI tasks: Use `general_ai` for questions not requiring external tools
    
    **Multi-tool Usage:**
    - Combine tools when it provides better results
    - For research tasks, consider using both `websearch` and `ask_website`
    - When processing documents, you might need `process_pdf` followed by analysis
    
    **Response Format:**
    Always respond with a JSON array within `<tool_call>` tags:
    
    <tool_call>[
        {{
            "name": "tool_name",
            "arguments": {{
                "parameter1": "value1",
                "parameter2": "value2"
            }}
        }}
    ]</tool_call>

    **Error Handling:**
    - If a request is unclear, use `general_ai` to ask for clarification
    - If no tools match, use `general_ai` with the original question
    - Never invent tools or parameters not in the available list
</instructions>

<examples>
    <example>
        <user>JARVIS, find the latest AI research papers and summarize them</user>
        <jarvis_response>
        <tool_call>[
            {{
                "name": "websearch",
                "arguments": {{
                    "query": "latest AI research papers 2024 arxiv"
                }}
            }}
        ]</tool_call>
        </jarvis_response>
    </example>
    
    <example>
        <user>JARVIS, check my internet speed and then search for faster internet plans</user>
        <jarvis_response>
        <tool_call>[
            {{
                "name": "check_internet_speed",
                "arguments": {{}}
            }},
            {{
                "name": "websearch",
                "arguments": {{
                    "query": "fast internet plans comparison 2024"
                }}
            }}
        ]</tool_call>
        </jarvis_response>
    </example>
    
    <example>
        <user>JARVIS, what's happening in tech news today?</user>
        <jarvis_response>
        <tool_call>[
            {{
                "name": "get_news",
                "arguments": {{
                    "topic": "technology",
                    "max_results": 5
                }}
            }}
        ]</tool_call>
        </jarvis_response>
    </example>
    
    <example>
        <user>JARVIS, tell me about yourself</user>
        <jarvis_response>
        <tool_call>[
            {{
                "name": "general_ai",
                "arguments": {{
                    "question": "tell me about yourself as JARVIS AI assistant"
                }}
            }}
        ]</tool_call>
        </jarvis_response>
    </example>
    
    <example>
        <user>JARVIS, extract information from this PDF and then search for related topics</user>
        <jarvis_response>
        <tool_call>[
            {{
                "name": "process_pdf",
                "arguments": {{
                    "input_path": "document.pdf",
                    "output_mode": "text"
                }}
            }}
        ]</tool_call>
        </jarvis_response>
    </example>
</examples>

<system_info>
    **Today's Date:** {current_date}
    **Knowledge Cutoff:** {self.knowledge_cutoff}
    **Available Tools:** {len(self.tools)}
</system_info>

<tools_list>
    You have access to the following tools:

{tools_description}
</tools_list>

<response_instructions>
Analyze the user's request carefully, select the most appropriate tools, and respond ONLY with the JSON structure within `<tool_call>` tags. 
Consider tool combinations for complex requests and always prioritize user intent over literal interpretation.
</response_instructions>
"""
        
    def _parse_function_call(self, response: str) -> FunctionCallData:
         try:
            start_tag: str = "<tool_call>["
            end_tag: str = "]</tool_call>"
            start_idx: int = response.find(start_tag)
            end_idx: int = response.rfind(end_tag)

            if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
                raise ValueError("No valid <tool_call> JSON structure found in the response.")

            json_str: str = response[start_idx + len(start_tag):end_idx].strip()

            # Safely load the JSON string
            parsed_response: Any = json.loads(json_str)

            if isinstance(parsed_response, list):
                 return {"tool_calls": parsed_response}
            elif isinstance(parsed_response, dict):
                return {"tool_calls": [parsed_response]}
            else:
                raise ValueError("<tool_call> should contain a list or a dictionary of tool calls.")

         except (ValueError, json.JSONDecodeError) as e:
            logging.error(f"Error parsing function call: %s", e)
            return {"error": str(e)}

    def execute_function(self, function_call_data: FunctionCallData) -> str:
         tool_calls: Optional[List[FunctionCall]] = function_call_data.get("tool_calls")

         if not tool_calls or not isinstance(tool_calls, list):
             return "Invalid tool_calls format."
        
         results: List[str] = []
         for tool_call in tool_calls:
            function_name: str = tool_call.get("name")
            arguments: Dict[str, Any] = tool_call.get("arguments", {})

            if not function_name or not isinstance(arguments, dict):
                results.append(f"Invalid tool call: {tool_call}")
                continue

            # Here you would implement the actual execution logic for each tool
            # For demonstration, we'll return a placeholder response
            results.append(f"Executed {function_name} with arguments {arguments}")

         return "; ".join(results)

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    @tools
    def web_search(query: str) -> str:
        """Search the web for current information on a given query"""
        return f"Searching the web for '{query}'"

    @tools
    def get_user_detail(name: str, age: int) -> str:
        """Get the user's name and age."""
        return f"User details: Name={name}, Age={age}"

    @tools
    def general_ai(question: str) -> str:
        """Use AI to answer general questions or perform tasks not requiring external tools"""
        return f"AI processing question: '{question}'"

    @tools
    def open_app(app_name: str) -> str:
       """Open a specified application on the system"""
       return f"Opening application: {app_name}"

    functions: List[Fn] = []
    local_vars: Dict[str, Any] = locals().copy() #Copy the local vars
    for name, obj in local_vars.items():
        if callable(obj) and hasattr(obj, '_is_tool'):
            sig = inspect.signature(obj)
            parameters = {param.name: "string" if param.annotation is inspect._empty else str(param.annotation).replace("<class '","").replace("'>","") for param in sig.parameters.values()}
            
            docstring = obj.__doc__ if obj.__doc__ else " "
            
            functions.append(Fn(name=name, description=docstring, parameters=parameters))


    agent: FunctionCallingAgent = FunctionCallingAgent(tools=functions)
    
    # Test cases
    test_messages: List[str] = [
        # "What's the weather like in New York today?",
        # "Who won the last FIFA World Cup?",
        # "Can you explain quantum computing?",
        # "What are the latest developments in AI?",
        # "Tell me a joke about programming.",
        # "What's the meaning of life?",
        "Get user details name as John and age as 30",

    ]

    for message in test_messages:
        # jp(message)
        function_call_data: FunctionCallData = agent.function_call_handler(message)
        jp(function_call_data)

        # if "error" not in function_call_data:
        #     result: str = agent.execute_function(function_call_data)
        #     print(f"Function Execution Result: {result}")
        # else:
        #     print(f"Error: {function_call_data['error']}")