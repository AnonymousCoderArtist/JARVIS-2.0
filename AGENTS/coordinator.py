"""
JARVIS Agent Coordination System

A comprehensive multi-agent architecture for intelligent task planning,
execution, and coordination with advanced error handling and learning.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum, auto
from datetime import datetime, timedelta
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
import time
from abc import ABC, abstractmethod

from .functioncall import FunctionCallingAgent
from .taskforge import TASKFORGE, ActionPlan, Step
from webscout.Provider import *


class AgentState(Enum):
    """Agent execution states."""
    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    WAITING = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class AgentType(Enum):
    """Types of agents in the system."""
    PLANNER = auto()
    EXECUTOR = auto()
    COORDINATOR = auto()
    MONITOR = auto()
    SPECIALIST = auto()


@dataclass
class Task:
    """Represents a task in the agent system."""
    id: str
    description: str
    priority: TaskPriority
    assigned_agent: Optional[str] = None
    state: AgentState = AgentState.IDLE
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AgentCapability:
    """Represents an agent's capability."""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    confidence: float
    execution_time_estimate: float  # seconds


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, agent_id: str, agent_type: AgentType, capabilities: List[AgentCapability]):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.state = AgentState.IDLE
        self.current_task: Optional[Task] = None
        self.task_history: List[Task] = []
        self.performance_metrics: Dict[str, float] = {
            "success_rate": 0.0,
            "average_execution_time": 0.0,
            "total_tasks": 0,
            "failed_tasks": 0
        }
        
        logging.info(f"Agent {agent_id} ({agent_type.name}) initialized with {len(capabilities)} capabilities")
    
    @abstractmethod
    async def execute_task(self, task: Task) -> Any:
        """Execute a specific task."""
        pass
    
    def can_handle_task(self, task: Task) -> Tuple[bool, float]:
        """Check if agent can handle a task and return confidence score."""
        # Simple capability matching - can be enhanced
        for capability in self.capabilities:
            if any(keyword in task.description.lower() for keyword in capability.name.lower().split()):
                return True, capability.confidence
        return False, 0.0
    
    def update_performance(self, task: Task, execution_time: float, success: bool):
        """Update agent performance metrics."""
        self.performance_metrics["total_tasks"] += 1
        
        if success:
            # Update success rate
            total = self.performance_metrics["total_tasks"]
            current_successes = total - self.performance_metrics["failed_tasks"]
            self.performance_metrics["success_rate"] = current_successes / total
            
            # Update average execution time
            current_avg = self.performance_metrics["average_execution_time"]
            self.performance_metrics["average_execution_time"] = (
                (current_avg * (total - 1) + execution_time) / total
            )
        else:
            self.performance_metrics["failed_tasks"] += 1
            total = self.performance_metrics["total_tasks"]
            failed = self.performance_metrics["failed_tasks"]
            self.performance_metrics["success_rate"] = (total - failed) / total
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status information."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.name,
            "state": self.state.name,
            "current_task": self.current_task.id if self.current_task else None,
            "capabilities": [cap.name for cap in self.capabilities],
            "performance": self.performance_metrics,
            "task_history_count": len(self.task_history)
        }


class PlannerAgent(BaseAgent):
    """Agent specialized in task planning and decomposition."""
    
    def __init__(self, agent_id: str = "planner_001"):
        capabilities = [
            AgentCapability(
                name="task_decomposition",
                description="Break down complex tasks into subtasks",
                input_types=["text", "task_description"],
                output_types=["action_plan", "task_list"],
                confidence=0.9,
                execution_time_estimate=2.0
            ),
            AgentCapability(
                name="dependency_analysis",
                description="Analyze task dependencies",
                input_types=["task_list"],
                output_types=["dependency_graph"],
                confidence=0.8,
                execution_time_estimate=1.0
            )
        ]
        super().__init__(agent_id, AgentType.PLANNER, capabilities)
        self.taskforge = TASKFORGE()
    
    async def execute_task(self, task: Task) -> ActionPlan:
        """Generate an action plan for the given task."""
        self.state = AgentState.PLANNING
        self.current_task = task
        
        try:
            logging.info(f"Planner agent {self.agent_id} planning task: {task.description}")
            
            # Use TASKFORGE to generate plan
            action_plan = self.taskforge._forge(task.description)
            
            self.state = AgentState.COMPLETED
            return action_plan
            
        except Exception as e:
            self.state = AgentState.ERROR
            task.error = str(e)
            logging.error(f"Planner agent {self.agent_id} failed: {e}")
            raise
        finally:
            self.current_task = None


class ExecutorAgent(BaseAgent):
    """Agent specialized in executing function calls and tools."""
    
    def __init__(self, agent_id: str = "executor_001", tools: List[Any] = None):
        capabilities = [
            AgentCapability(
                name="function_calling",
                description="Execute function calls and tools",
                input_types=["function_call", "tool_request"],
                output_types=["function_result", "tool_output"],
                confidence=0.95,
                execution_time_estimate=3.0
            ),
            AgentCapability(
                name="web_search",
                description="Search the web for information",
                input_types=["search_query"],
                output_types=["search_results"],
                confidence=0.9,
                execution_time_estimate=5.0
            ),
            AgentCapability(
                name="data_processing",
                description="Process and analyze data",
                input_types=["data", "file"],
                output_types=["processed_data", "analysis"],
                confidence=0.8,
                execution_time_estimate=10.0
            )
        ]
        super().__init__(agent_id, AgentType.EXECUTOR, capabilities)
        self.function_agent = FunctionCallingAgent(tools or [])
        self.tools = tools or []
    
    async def execute_task(self, task: Task) -> Any:
        """Execute a function calling task."""
        self.state = AgentState.EXECUTING
        self.current_task = task
        
        try:
            logging.info(f"Executor agent {self.agent_id} executing task: {task.description}")
            
            # Use function calling agent
            result = self.function_agent.function_call_handler(task.description)
            
            if "error" in result:
                raise Exception(result["error"])
            
            self.state = AgentState.COMPLETED
            return result
            
        except Exception as e:
            self.state = AgentState.ERROR
            task.error = str(e)
            logging.error(f"Executor agent {self.agent_id} failed: {e}")
            raise
        finally:
            self.current_task = None


class MonitorAgent(BaseAgent):
    """Agent specialized in monitoring and health checking."""
    
    def __init__(self, agent_id: str = "monitor_001"):
        capabilities = [
            AgentCapability(
                name="system_monitoring",
                description="Monitor system health and performance",
                input_types=["system_metrics"],
                output_types=["health_report"],
                confidence=0.9,
                execution_time_estimate=1.0
            ),
            AgentCapability(
                name="error_detection",
                description="Detect and report errors",
                input_types=["log_data", "error_signals"],
                output_types=["error_report"],
                confidence=0.85,
                execution_time_estimate=0.5
            )
        ]
        super().__init__(agent_id, AgentType.MONITOR, capabilities)
        self.health_checks: List[Callable] = []
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute monitoring task."""
        self.state = AgentState.EXECUTING
        self.current_task = task
        
        try:
            logging.info(f"Monitor agent {self.agent_id} monitoring: {task.description}")
            
            # Perform health checks
            health_report = {
                "timestamp": datetime.now().isoformat(),
                "checks": [],
                "overall_status": "healthy"
            }
            
            for check in self.health_checks:
                try:
                    check_result = check()
                    health_report["checks"].append({
                        "name": check.__name__,
                        "status": "pass",
                        "result": check_result
                    })
                except Exception as e:
                    health_report["checks"].append({
                        "name": check.__name__,
                        "status": "fail",
                        "error": str(e)
                    })
                    health_report["overall_status"] = "unhealthy"
            
            self.state = AgentState.COMPLETED
            return health_report
            
        except Exception as e:
            self.state = AgentState.ERROR
            task.error = str(e)
            logging.error(f"Monitor agent {self.agent_id} failed: {e}")
            raise
        finally:
            self.current_task = None
    
    def add_health_check(self, check_function: Callable):
        """Add a health check function."""
        self.health_checks.append(check_function)


class SpecialistAgent(BaseAgent):
    """Agent specialized in specific domains."""
    
    def __init__(self, agent_id: str, specialty: str, model: str = "openai-large"):
        capabilities = [
            AgentCapability(
                name=f"{specialty}_specialist",
                description=f"Specialized knowledge in {specialty}",
                input_types=["text", "question"],
                output_types=["specialized_response"],
                confidence=0.95,
                execution_time_estimate=5.0
            )
        ]
        super().__init__(agent_id, AgentType.SPECIALIST, capabilities)
        self.specialty = specialty
        self.ai = C4ai(
            model=model,
            is_conversation=False,
            system_prompt=f"You are a specialist in {specialty}. Provide expert-level responses."
        )
    
    async def execute_task(self, task: Task) -> str:
        """Execute specialist task."""
        self.state = AgentState.EXECUTING
        self.current_task = task
        
        try:
            logging.info(f"Specialist agent {self.agent_id} ({self.specialty}) handling: {task.description}")
            
            # Generate specialized response
            response = "".join(self.ai.chat(task.description))
            
            self.state = AgentState.COMPLETED
            return response
            
        except Exception as e:
            self.state = AgentState.ERROR
            task.error = str(e)
            logging.error(f"Specialist agent {self.agent_id} failed: {e}")
            raise
        finally:
            self.current_task = None


class AgentCoordinator:
    """Central coordinator for managing multiple agents and tasks."""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.failed_tasks: List[Task] = []
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running_tasks: Dict[str, Future] = {}
        
        # Default agents
        self._initialize_default_agents()
        
        logging.info("Agent Coordinator initialized")
    
    def _initialize_default_agents(self):
        """Initialize default agents."""
        # Add planner agent
        planner = PlannerAgent()
        self.register_agent(planner)
        
        # Add executor agent
        executor = ExecutorAgent()
        self.register_agent(executor)
        
        # Add monitor agent
        monitor = MonitorAgent()
        self.register_agent(monitor)
        
        # Add some specialist agents
        python_specialist = SpecialistAgent("python_specialist", "Python programming")
        self.register_agent(python_specialist)
        
        ai_specialist = SpecialistAgent("ai_specialist", "Artificial Intelligence and Machine Learning")
        self.register_agent(ai_specialist)
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the coordinator."""
        self.agents[agent.agent_id] = agent
        logging.info(f"Registered agent: {agent.agent_id} ({agent.agent_type.name})")
    
    def create_task(self, description: str, priority: TaskPriority = TaskPriority.NORMAL,
                   dependencies: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        """Create a new task."""
        task_id = f"task_{int(datetime.now().timestamp())}_{len(self.tasks)}"
        
        task = Task(
            id=task_id,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {}
        )
        
        self.tasks[task_id] = task
        self._add_to_queue(task)
        
        logging.info(f"Created task {task_id}: {description}")
        return task_id
    
    def _add_to_queue(self, task: Task):
        """Add task to queue in priority order."""
        # Insert based on priority
        inserted = False
        for i, queued_task in enumerate(self.task_queue):
            if task.priority.value > queued_task.priority.value:
                self.task_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.task_queue.append(task)
    
    def assign_task(self, task: Task) -> Optional[BaseAgent]:
        """Assign a task to the best available agent."""
        best_agent = None
        best_score = 0.0
        
        for agent in self.agents.values():
            if agent.state == AgentState.IDLE:
                can_handle, confidence = agent.can_handle_task(task)
                if can_handle:
                    # Consider agent performance in scoring
                    score = confidence * agent.performance_metrics["success_rate"]
                    if score > best_score:
                        best_score = score
                        best_agent = agent
        
        if best_agent:
            task.assigned_agent = best_agent.agent_id
            best_agent.current_task = task
            logging.info(f"Assigned task {task.id} to agent {best_agent.agent_id}")
        
        return best_agent
    
    async def execute_task_async(self, task: Task, agent: BaseAgent) -> Any:
        """Execute a task asynchronously."""
        start_time = time.time()
        
        try:
            task.state = AgentState.EXECUTING
            task.started_at = datetime.now()
            
            result = await agent.execute_task(task)
            
            task.state = AgentState.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            execution_time = time.time() - start_time
            agent.update_performance(task, execution_time, True)
            agent.task_history.append(task)
            
            self.completed_tasks.append(task)
            
            logging.info(f"Task {task.id} completed successfully in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            task.state = AgentState.ERROR
            task.error = str(e)
            task.completed_at = datetime.now()
            
            execution_time = time.time() - start_time
            agent.update_performance(task, execution_time, False)
            agent.task_history.append(task)
            
            self.failed_tasks.append(task)
            
            logging.error(f"Task {task.id} failed after {execution_time:.2f}s: {e}")
            raise
    
    def process_queue(self):
        """Process the task queue."""
        while self.task_queue:
            task = self.task_queue[0]
            
            # Check dependencies
            if not self._dependencies_satisfied(task):
                # Move to end of queue if dependencies not satisfied
                self.task_queue.append(self.task_queue.pop(0))
                continue
            
            # Try to assign task
            agent = self.assign_task(task)
            if agent:
                # Remove from queue
                self.task_queue.pop(0)
                
                # Execute task
                future = self.executor.submit(asyncio.run, self.execute_task_async(task, agent))
                self.running_tasks[task.id] = future
            else:
                # No available agent, try next task
                break
    
    def _dependencies_satisfied(self, task: Task) -> bool:
        """Check if task dependencies are satisfied."""
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.state != AgentState.COMPLETED:
                    return False
        return True
    
    def run_coordinator(self, max_iterations: int = 100):
        """Run the coordinator for task processing."""
        iteration = 0
        
        while self.task_queue and iteration < max_iterations:
            self.process_queue()
            
            # Check completed futures
            completed_futures = []
            for task_id, future in self.running_tasks.items():
                if future.done():
                    completed_futures.append(task_id)
            
            # Remove completed futures
            for task_id in completed_futures:
                del self.running_tasks[task_id]
            
            # Wait a bit before next iteration
            time.sleep(0.1)
            iteration += 1
        
        # Wait for remaining tasks to complete
        for future in self.running_tasks.values():
            try:
                future.result(timeout=30)
            except Exception as e:
                logging.error(f"Task failed: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "agents": {agent_id: agent.get_status() for agent_id, agent in self.agents.items()},
            "tasks": {
                "total": len(self.tasks),
                "queued": len(self.task_queue),
                "running": len(self.running_tasks),
                "completed": len(self.completed_tasks),
                "failed": len(self.failed_tasks)
            },
            "performance": {
                "success_rate": len(self.completed_tasks) / len(self.tasks) if self.tasks else 0.0,
                "average_agent_utilization": sum(
                    1 for agent in self.agents.values() if agent.state != AgentState.IDLE
                ) / len(self.agents) if self.agents else 0.0
            }
        }
    
    def shutdown(self):
        """Shutdown the coordinator and all agents."""
        logging.info("Shutting down Agent Coordinator")
        
        # Cancel running tasks
        for future in self.running_tasks.values():
            future.cancel()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Reset agent states
        for agent in self.agents.values():
            agent.state = AgentState.IDLE
            agent.current_task = None


class EnhancedJARVIS:
    """Enhanced JARVIS with agent coordination."""
    
    def __init__(self):
        self.coordinator = AgentCoordinator()
        self.conversation_history = []
        
        logging.info("Enhanced JARVIS with Agent Coordination initialized")
    
    def process_request(self, user_input: str, priority: TaskPriority = TaskPriority.NORMAL) -> Dict[str, Any]:
        """Process a user request using the agent system."""
        # Create task
        task_id = self.coordinator.create_task(
            description=user_input,
            priority=priority,
            metadata={"type": "user_request", "timestamp": datetime.now().isoformat()}
        )
        
        # Process the queue
        self.coordinator.run_coordinator(max_iterations=10)
        
        # Get task result
        task = self.coordinator.tasks[task_id]
        
        # Store in conversation history
        self.conversation_history.append({
            "user_input": user_input,
            "task_id": task_id,
            "result": task.result,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "task_id": task_id,
            "result": task.result,
            "state": task.state.name,
            "error": task.error
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get enhanced JARVIS status."""
        return {
            "coordinator_status": self.coordinator.get_system_status(),
            "conversation_history_length": len(self.conversation_history),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create enhanced JARVIS
    jarvis = EnhancedJARVIS()
    
    # Process some requests
    result1 = jarvis.process_request("Search for Python tutorials")
    print("Result 1:", result1)
    
    result2 = jarvis.process_request("Explain machine learning", TaskPriority.HIGH)
    print("Result 2:", result2)
    
    # Get system status
    status = jarvis.get_status()
    print("System Status:", json.dumps(status, indent=2, default=str))
    
    # Shutdown
    jarvis.coordinator.shutdown()