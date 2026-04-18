"""Agent Coordinator for multi-agent orchestration"""

from core.llm_sdk.context_length_manager import context_length_manager
from core.memory.conversation_manager import ConversationManager
from core.tools.registry import ToolRegistry

from .base import BaseAgent


class AgentCoordinator:
    """Coordinates multiple agents for complex task execution with conversation history"""

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        tool_registry: ToolRegistry | None = None,
        model: str | None = None
    ):
        self.agents = agents
        self.tool_registry = tool_registry
        self.task_history: list[dict] = []
        self.current_task: dict | None = None
        self.model = model or "claude-3-5-sonnet-20241022"
        # Callbacks for streaming and tool calls
        self.stream_callback: callable | None = None
        self.tool_call_callback: callable | None = None
        self.tool_result_callback: callable | None = None

        # Initialize conversation manager with auto-summarization
        self.conversation_manager = ConversationManager(
            max_history=50,
            context_threshold=0.75,  # Summarize at 75% context usage
            summarization_callback=self._generate_summary
        )

        # Set max context tokens based on model
        token_limits = context_length_manager.get_token_limits(self.model)
        self.conversation_manager.set_max_context_tokens(token_limits.max_input_tokens)

        # Link coordinator to agents if they support it
        for agent in self.agents.values():
            if hasattr(agent, "update_context"):
                agent.update_context("coordinator", self)

    async def execute_task(self, task: str, context: dict | None = None) -> str:
        """
        Execute a task by coordinating agents with conversation history

        Args:
            task: Task description
            context: Optional context

        Returns:
            Final result from task execution
        """
        # Add user message to conversation history
        self.conversation_manager.add_message("user", task, context or {})

        # 1. Analyze task and select appropriate agent
        agent_name = self.select_agent(task)

        if not agent_name or agent_name not in self.agents:
            error_msg = "No suitable agent found for this task"
            self.conversation_manager.add_message("assistant", error_msg)
            return error_msg

        agent = self.agents[agent_name]

        # 2. Create task entry
        task_entry = {
            "id": len(self.task_history),
            "task": task,
            "agent": agent_name,
            "context": context,
            "status": "in_progress"
        }
        self.current_task = task_entry

        # 3. Get conversation history for context
        conversation_history = self.conversation_manager.get_messages()

        # 4. Execute task with the selected agent
        try:
            # Set callbacks on agent
            agent.stream_callback = self.stream_callback
            agent.tool_call_callback = self.tool_call_callback
            agent.tool_result_callback = self.tool_result_callback

            # Pass conversation history to agent if supported
            agent_context = context or {}
            agent_context["conversation_history"] = conversation_history

            result = await agent.process(task, agent_context)

            # Extract token count if available from LLM response
            token_count = None
            if hasattr(result, 'usage') and result.usage:
                token_count = result.usage.get('total_tokens')
            elif isinstance(result, dict) and 'usage' in result:
                token_count = result['usage'].get('total_tokens')
            elif isinstance(result, dict) and 'token_count' in result:
                token_count = result['token_count']

            task_entry["status"] = "completed"
            task_entry["result"] = result
            task_entry["token_count"] = token_count

            self.task_history.append(task_entry)
            self.current_task = None

            # Add assistant response to conversation history with token count
            result_text = str(result) if not isinstance(result, str) else result
            self.conversation_manager.add_message("assistant", result_text, token_count=token_count)

            return result

        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            task_entry["status"] = "failed"
            task_entry["error"] = str(e)

            self.task_history.append(task_entry)
            self.current_task = None

            # Add error to conversation history
            self.conversation_manager.add_message("assistant", error_msg)

            return error_msg

    async def _generate_summary(self, messages: list[dict]) -> tuple:
        """
        Generate a summary of conversation history using the LLM

        Args:
            messages: List of message dictionaries to summarize

        Returns:
            Tuple of (summary_text, token_count)
        """
        # Get a default agent to use for summarization
        agent = next(iter(self.agents.values()), None)
        if not agent:
            return "Summary unavailable: No agent available", 0

        # Create summarization prompt
        summary_prompt = [
            {
                "role": "system",
                "content": "You are a conversation summarizer. Summarize the following conversation concisely, preserving key information, decisions made, and important context. Keep the summary under 500 words."
            },
            {
                "role": "user",
                "content": "Summarize this conversation:\n\n" + "\n\n".join([
                    f"{m['role']}: {m['content']}" for m in messages
                ])
            }
        ]

        try:
            # Try to get response with usage information
            response = await agent.llm.generate(
                messages=summary_prompt,
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                return_usage=True
            )

            # Extract token count if available
            token_count = 0
            if hasattr(response, 'usage') and response.usage:
                token_count = response.usage.get('total_tokens', 0)
            elif isinstance(response, dict) and 'usage' in response:
                token_count = response['usage'].get('total_tokens', 0)

            summary_text = str(response) if not isinstance(response, str) else response
            return summary_text, token_count

        except Exception as e:
            print(f"Failed to generate summary: {e}")
            return f"Summary generation failed. Original conversation had {len(messages)} messages.", 0

    def select_agent(self, task: str) -> str | None:
        """
        Select the best agent for a task using keyword scoring

        Args:
            task: Task description

        Returns:
            Agent name or None if no suitable agent found
        """
        task_lower = task.lower()

        # Keyword sets for different domains
        keywords = {
            "coding": [
                "code", "programming", "debug", "test", "refactor", "python", "javascript",
                "git", "repo", "file edit", "replace", "bash", "shell", "script"
            ],
            "knowledge": [
                "research", "information", "summarize", "find", "search", "who", "what",
                "explain", "report", "document", "pdf", "web", "fetch"
            ]
        }

        scores = dict.fromkeys(self.agents.keys(), 0)

        for agent_name in scores.keys():
            # Check domain keywords
            if agent_name in keywords:
                for kw in keywords[agent_name]:
                    if kw in task_lower:
                        scores[agent_name] += 1

            # Bonus for explicit mentions
            if agent_name in task_lower:
                scores[agent_name] += 5

        # Get agent with highest score
        if not scores or max(scores.values()) == 0:
            # Fallback based on simple logic
            if "coding" in self.agents and any(c in task_lower for c in ["file", "edit", "run"]):
                return "coding"
            return list(self.agents.keys())[0] if self.agents else None

        return max(scores, key=scores.get)

    def get_agent(self, name: str) -> BaseAgent | None:
        """Get an agent by name"""
        return self.agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names"""
        return list(self.agents.keys())

    def get_conversation_stats(self) -> dict:
        """Get conversation statistics including context usage"""
        return self.conversation_manager.get_stats()

    def get_conversation_history(self, limit: int | None = None) -> list[dict]:
        """
        Get conversation history

        Args:
            limit: Optional limit on number of messages

        Returns:
            List of message dictionaries
        """
        return self.conversation_manager.get_messages(limit)

    def clear_conversation(self):
        """Clear conversation history except system messages"""
        self.conversation_manager.clear()
