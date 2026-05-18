"""HF Jobs tool — manage Hugging Face Training Jobs.

Ported from huggingface/ml-intern agent/tools/jobs_tool.py.

This is a simplified port that covers the core operations: submit, status, logs, stop, list.
The full ml-intern jobs tool has more complex features (scheduled jobs, approval workflows)
that require the ml-intern session infrastructure.
"""

from __future__ import annotations

import logging
from typing import Any

from jarvis.api import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

# Hardware flavors
CPU_FLAVORS = ["cpu-basic", "cpu-upgrade"]
GPU_FLAVORS = [
    "t4-small", "t4-medium", "a10g-small", "a10g-large", "a10g-largex2", "a10g-largex4",
    "a100-large", "a100x4", "a100x8", "l4x1", "l4x4", "l40sx1", "l40sx4", "l40sx8",
]
ALL_FLAVORS = CPU_FLAVORS + GPU_FLAVORS

GPU_FLAVORS_DESC = (
    "t4-small(4vCPU/15GB/GPU 16GB), t4-medium(8vCPU/30GB/GPU 16GB), "
    "a10g-small(4vCPU/15GB/GPU 24GB), a10g-large(12vCPU/46GB/GPU 24GB), "
    "a10g-largex2(24vCPU/92GB/GPU 48GB), a10g-largex4(48vCPU/184GB/GPU 96GB), "
    "a100-large(12vCPU/142GB/GPU 80GB), a100x4(48vCPU/568GB/GPU 320GB), a100x8(96vCPU/1136GB/GPU 640GB), "
    "l4x1(8vCPU/30GB/GPU 24GB), l4x4(48vCPU/186GB/GPU 96GB), "
    "l40sx1(8vCPU/62GB/GPU 48GB), l40sx4(48vCPU/382GB/GPU 192GB), l40sx8(192vCPU/1534GB/GPU 384GB)"
)


class HfJobsTool(BaseTool):
    name = "hf_jobs"
    description = (
        "Submit and manage Hugging Face Training Jobs.\n\n"
        "Operations:\n"
        "- submit: Submit a new training job\n"
        "- status: Check job status\n"
        "- logs: Get job logs\n"
        "- stop: Stop a running job\n"
        "- list: List your jobs\n\n"
        f"GPU flavors: {GPU_FLAVORS_DESC}\n\n"
        "IMPORTANT:\n"
        "- Always set timeout to at least 7200 (2 hours) for training jobs\n"
        "- Always include push_to_hub=True and hub_model_id in training args\n"
        "- Test with a small job before submitting large ones\n"
        "- Use Trackio for monitoring (report_to='trackio')"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["submit", "status", "logs", "stop", "list"],
                "description": "Operation to execute",
            },
            "job_id": {
                "type": "string",
                "description": "Job ID for status/logs/stop operations",
            },
            "command": {
                "type": "string",
                "description": "Command to run (for submit)",
            },
            "flavor": {
                "type": "string",
                "enum": ALL_FLAVORS,
                "description": "Hardware flavor (for submit)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 7200, min: 300, max: 86400)",
            },
            "namespace": {
                "type": "string",
                "description": "Namespace/org for the job (default: your user)",
            },
            "image": {
                "type": "string",
                "description": "Docker image for the job (default: HF auto)",
            },
            "env": {
                "type": "object",
                "description": "Environment variables for the job",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["operation"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        operation = getattr(input_data, "operation", None)
        if not operation:
            return ToolOutput(success=False, result=None, error="operation is required")

        try:
            from huggingface_hub import HfApi
        except ImportError:
            return ToolOutput(success=False, result=None, error="huggingface_hub is not installed")

        import os
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return ToolOutput(success=False, result=None, error="HF_TOKEN not set")

        api = HfApi(token=hf_token)

        try:
            if operation == "submit":
                return await self._submit(api, input_data)
            elif operation == "status":
                return await self._status(api, input_data)
            elif operation == "logs":
                return await self._logs(api, input_data)
            elif operation == "stop":
                return await self._stop(api, input_data)
            elif operation == "list":
                return await self._list(api, input_data)
            else:
                return ToolOutput(success=False, result=None, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")

    async def _submit(self, api, input_data) -> ToolOutput:
        import asyncio
        command = getattr(input_data, "command", None)
        flavor = getattr(input_data, "flavor", None)
        timeout = getattr(input_data, "timeout", 7200)
        namespace = getattr(input_data, "namespace", None)
        image = getattr(input_data, "image", None)
        env = getattr(input_data, "env", None)

        if not command:
            return ToolOutput(success=False, result=None, error="command is required for submit")
        if not flavor:
            return ToolOutput(success=False, result=None, error="flavor is required for submit")

        kwargs: dict[str, Any] = {
            "command": command,
            "flavor": flavor,
            "timeout": timeout,
        }
        if namespace:
            kwargs["namespace"] = namespace
        if image:
            kwargs["image"] = image
        if env:
            kwargs["env"] = env

        job = await asyncio.to_thread(api.run_job, **kwargs)
        return ToolOutput(
            success=True,
            result=(
                f"**Job submitted:** {job.id}\n"
                f"**Status:** {job.status}\n"
                f"**Flavor:** {flavor}\n"
                f"**Timeout:** {timeout}s\n"
                f"https://huggingface.co/jobs/{job.id}"
            ),
        )

    async def _status(self, api, input_data) -> ToolOutput:
        import asyncio
        job_id = getattr(input_data, "job_id", None)
        if not job_id:
            return ToolOutput(success=False, result=None, error="job_id is required")
        job = await asyncio.to_thread(api.get_job, job_id)
        return ToolOutput(
            success=True,
            result=(
                f"**Job:** {job.id}\n"
                f"**Status:** {job.status}\n"
                f"**Flavor:** {getattr(job, 'flavor', 'unknown')}\n"
                f"https://huggingface.co/jobs/{job.id}"
            ),
        )

    async def _logs(self, api, input_data) -> ToolOutput:
        import asyncio
        job_id = getattr(input_data, "job_id", None)
        if not job_id:
            return ToolOutput(success=False, result=None, error="job_id is required")
        logs = await asyncio.to_thread(api.get_job_logs, job_id)
        # Truncate if too long
        if len(logs) > 25000:
            logs = logs[:10000] + "\n\n... (truncated) ...\n\n" + logs[-10000:]
        return ToolOutput(success=True, result=f"**Logs for {job_id}:**\n```\n{logs}\n```")

    async def _stop(self, api, input_data) -> ToolOutput:
        import asyncio
        job_id = getattr(input_data, "job_id", None)
        if not job_id:
            return ToolOutput(success=False, result=None, error="job_id is required")
        await asyncio.to_thread(api.cancel_job, job_id)
        return ToolOutput(success=True, result=f"**Job stopped:** {job_id}")

    async def _list(self, api, input_data) -> ToolOutput:
        import asyncio
        namespace = getattr(input_data, "namespace", None)
        kwargs: dict[str, Any] = {}
        if namespace:
            kwargs["namespace"] = namespace
        jobs = await asyncio.to_thread(api.list_jobs, **kwargs)
        if not jobs:
            return ToolOutput(success=True, result="No jobs found.")
        lines = [f"**Found {len(jobs)} job(s):**\n"]
        for job in jobs[:20]:
            lines.append(f"- **{job.id}** — {job.status} — {getattr(job, 'flavor', 'unknown')}")
        if len(jobs) > 20:
            lines.append(f"\n... and {len(jobs) - 20} more")
        return ToolOutput(success=True, result="\n".join(lines))
