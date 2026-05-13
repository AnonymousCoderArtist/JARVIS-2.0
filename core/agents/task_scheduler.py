"""Task scheduling and decomposition for JARVIS agents"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TaskStatus(Enum):
    """Status of a task"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """Represents a single task in the scheduler"""

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None


class TaskScheduler:
    """Decomposes and schedules tasks for parallel execution"""

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.tasks: dict[str, Task] = {}
        self._task_counter = 0

    def decompose(self, objective: str) -> list[Task]:
        """
        Decompose an objective into subtasks using keyword-based analysis.

        Args:
            objective: High-level task description

        Returns:
            List of decomposed Task objects
        """
        parts = re.split(r"[;,]|\band\b|\bthen\b", objective)
        parts = [p.strip() for p in parts if p.strip()]

        tasks = []
        for i, part in enumerate(parts):
            part_lower = part.lower()
            deps = []

            for match in re.finditer(r"task[_-]?(\d+)", part_lower):
                dep_id = f"task_{match.group(1)}"
                if dep_id in self.tasks:
                    deps.append(dep_id)

            priority = 10 - i
            if any(kw in part_lower for kw in ["important", "critical", "urgent"]):
                priority += 20
            if any(kw in part_lower for kw in ["optional", "nice-to-have"]):
                priority -= 5

            task_id = f"task_{i}"
            task = Task(
                id=task_id,
                description=part,
                priority=priority,
                dependencies=deps,
            )
            tasks.append(task)
            self.tasks[task_id] = task
            self._task_counter += 1

        return tasks

    def schedule(self, tasks: list[Task]) -> list[list[Task]]:
        """
        Schedule tasks into execution batches respecting dependencies.

        Uses topological sorting with priority ordering.

        Args:
            tasks: List of tasks to schedule

        Returns:
            List of batches for parallel execution
        """
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        dependents: dict[str, list[str]] = {t.id: [] for t in tasks}

        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in dependents:
                    dependents[dep_id].append(task.id)
                    in_degree[task.id] += 1

        batches = []
        remaining = set(t.id for t in tasks)

        while remaining:
            ready = [
                t for t in tasks
                if t.id in remaining and in_degree[t.id] == 0
            ]

            if not ready:
                ready = [t for t in tasks if t.id in remaining]

            ready.sort(key=lambda t: (-t.priority, t.description.lower()))
            batch = ready[:self.max_concurrent]
            batches.append(batch)

            for task in batch:
                remaining.remove(task.id)
                for dependent_id in dependents[task.id]:
                    if dependent_id in remaining:
                        in_degree[dependent_id] -= 1

        return batches

    async def run(
        self,
        objective: str,
        executor_fn: Callable[[Task], Any],
    ) -> dict[str, Any]:
        """
        Decompose, schedule, and execute tasks.

        Args:
            objective: High-level task description
            executor_fn: Async callable that takes a Task and returns a result dict

        Returns:
            Dictionary mapping task IDs to their results
        """
        tasks = self.decompose(objective)
        batches = self.schedule(tasks)

        results = {}
        for batch in batches:
            coroutines = [executor_fn(task) for task in batch]
            batch_results = await asyncio.gather(*coroutines, return_exceptions=True)

            for task, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                else:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                results[task.id] = result

        return results

    async def decompose_and_plan(self, objective: str) -> list[dict[str, Any]]:
        """
        Decompose an objective and return a structured plan.

        Args:
            objective: High-level task description

        Returns:
            List of planned steps with descriptions and dependencies
        """
        tasks = self.decompose(objective)
        return [
            {
                "id": t.id,
                "description": t.description,
                "priority": t.priority,
                "dependencies": t.dependencies,
                "status": t.status.value,
            }
            for t in tasks
        ]
