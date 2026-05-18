"""HF Jobs tool — manage Hugging Face Training Jobs.

Ported from huggingface/ml-intern agent/tools/jobs_tool.py.
Full feature set: UV commands, scheduled jobs, log streaming, trackio seeding,
billing error detection, and all job lifecycle operations.
"""

from __future__ import annotations

import asyncio
import base64
import http.client
import json
import logging
import re
import shlex
from datetime import datetime, timezone
from typing import Any

import httpx
from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

from jarvis.api import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

CPU_FLAVORS = ["cpu-basic", "cpu-upgrade"]
GPU_FLAVORS = [
    "t4-small", "t4-medium", "a10g-small", "a10g-large",
    "a10g-largex2", "a10g-largex4", "a100-large", "a100x4", "a100x8",
    "l4x1", "l4x4", "l40sx1", "l40sx4", "l40sx8",
]
SPECIALIZED_FLAVORS = ["inf2x6"]
ALL_FLAVORS = CPU_FLAVORS + GPU_FLAVORS + SPECIALIZED_FLAVORS

CPU_FLAVORS_DESC = "cpu-basic(2vCPU/16GB), cpu-upgrade(8vCPU/32GB)"
GPU_FLAVORS_DESC = (
    "t4-small(4vCPU/15GB/GPU 16GB), t4-medium(8vCPU/30GB/GPU 16GB), "
    "a10g-small(4vCPU/15GB/GPU 24GB), a10g-large(12vCPU/46GB/GPU 24GB), "
    "a10g-largex2(24vCPU/92GB/GPU 48GB), a10g-largex4(48vCPU/184GB/GPU 96GB), "
    "a100-large(12vCPU/142GB/GPU 80GB), a100x4(48vCPU/568GB/GPU 320GB), a100x8(96vCPU/1136GB/GPU 640GB), "
    "l4x1(8vCPU/30GB/GPU 24GB), l4x4(48vCPU/186GB/GPU 96GB), "
    "l40sx1(8vCPU/62GB/GPU 48GB), l40sx4(48vCPU/382GB/GPU 192GB), l40sx8(192vCPU/1534GB/GPU 384GB)"
)

UV_DEFAULT_IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"

_DEFAULT_ENV = {
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "TQDM_DISABLE": "1",
    "TRANSFORMERS_VERBOSITY": "warning",
    "HF_HUB_ENABLE_HF_TRANSFER": "1",
    "UV_NO_PROGRESS": "1",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _is_billing_error(err_str: str) -> bool:
    return "billing" in err_str.lower() or "credits" in err_str.lower() or "payment" in err_str.lower()


def _filter_uv_install_output(logs: list[str]) -> list[str]:
    install_pattern = re.compile(r"^Installed\s+\d+\s+packages?\s+in\s+\d+(?:\.\d+)?\s*(?:ms|s)$")
    install_line_idx = None
    for idx, line in enumerate(logs):
        if install_pattern.match(line.strip()):
            install_line_idx = idx
            break
    if install_line_idx is not None and install_line_idx > 0:
        return ["[installs truncated]"] + logs[install_line_idx:]
    return logs


def _build_uv_command(
    script: str,
    with_deps: list[str] | None = None,
    python: str | None = None,
    script_args: list[str] | None = None,
) -> list[str]:
    parts = ["uv", "run"]
    if with_deps:
        for dep in with_deps:
            parts.extend(["--with", dep])
    if python:
        parts.extend(["-p", python])
    parts.append(script)
    if script_args:
        parts.extend(script_args)
    return parts


def _wrap_inline_script(
    script: str,
    with_deps: list[str] | None = None,
    python: str | None = None,
    script_args: list[str] | None = None,
) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("utf-8")
    uv_command = _build_uv_command("-", with_deps, python, script_args)
    uv_command_str = " ".join(uv_command)
    return f'echo "{encoded}" | base64 -d | {uv_command_str}'


def _resolve_uv_command(
    script: str,
    with_deps: list[str] | None = None,
    python: str | None = None,
    script_args: list[str] | None = None,
) -> list[str]:
    if script.startswith("http://") or script.startswith("https://"):
        return _build_uv_command(script, with_deps, python, script_args)
    if "\n" in script:
        wrapped = _wrap_inline_script(script, with_deps, python, script_args)
        return ["/bin/sh", "-lc", wrapped]
    return _build_uv_command(script, with_deps, python, script_args)


def _ensure_hf_transfer_dependency(deps: list[str] | None) -> list[str]:
    if isinstance(deps, list):
        if "hf-transfer" not in deps:
            return deps + ["hf-transfer"]
        return deps.copy()
    return ["hf-transfer"]


def _job_info_to_dict(job_info) -> dict[str, Any]:
    return {
        "id": job_info.id,
        "status": {"stage": job_info.status.stage, "message": job_info.status.message},
        "command": job_info.command,
        "createdAt": job_info.created_at.isoformat(),
        "dockerImage": job_info.docker_image,
        "spaceId": job_info.space_id,
        "hardware_flavor": job_info.flavor,
        "owner": {"name": job_info.owner.name},
    }


def _scheduled_job_info_to_dict(sj) -> dict[str, Any]:
    job_spec = sj.job_spec
    last_run = None
    next_run = None
    if sj.status:
        if sj.status.last_job and sj.status.last_job.created_at:
            last_run = sj.status.last_job.created_at.isoformat()
        if sj.status.next_job_run_at:
            next_run = sj.status.next_job_run_at.isoformat()
    return {
        "id": sj.id,
        "schedule": sj.schedule,
        "suspend": sj.suspend,
        "lastRun": last_run,
        "nextRun": next_run,
        "jobSpec": {
            "dockerImage": job_spec.docker_image,
            "spaceId": job_spec.space_id,
            "command": job_spec.command or [],
            "hardware_flavor": job_spec.flavor or "cpu-basic",
        },
    }


class HfJobsTool(BaseTool):
    name = "hf_jobs"
    description = (
        "Execute Python scripts or Docker containers on Hugging Face cloud infrastructure.\n\n"
        "Two modes (mutually exclusive): Python mode (script + dependencies) or Docker mode (command + image). "
        "Provide exactly ONE of 'script' or 'command'.\n\n"
        "BEFORE submitting training/fine-tuning jobs:\n"
        "- You MUST have called github_find_examples + github_read_file to find a working reference.\n"
        "- You MUST have validated dataset format via hf_inspect_dataset.\n"
        "- Training config MUST include push_to_hub=True and hub_model_id.\n"
        "  Job storage is EPHEMERAL — all files are deleted when the job ends.\n\n"
        "BATCH/ABLATION JOBS: Submit ONE job first. Check logs to confirm it starts.\n"
        "Only then submit the remaining jobs.\n\n"
        "Operations: run, ps, logs, inspect, cancel, "
        "scheduled run, scheduled ps, scheduled inspect, "
        "scheduled delete, scheduled suspend, scheduled resume.\n\n"
        f"Hardware — CPU: {CPU_FLAVORS_DESC}. GPU: {GPU_FLAVORS_DESC}.\n\n"
        "OOM RECOVERY:\n"
        "1. Reduce per_device_train_batch_size and increase gradient_accumulation_steps\n"
        "2. Enable gradient_checkpointing=True\n"
        "3. Upgrade to larger GPU\n"
        "Do NOT switch training methods or reduce max_length without approval."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "run", "ps", "logs", "inspect", "cancel",
                    "scheduled run", "scheduled ps", "scheduled inspect",
                    "scheduled delete", "scheduled suspend", "scheduled resume",
                ],
                "description": "Operation to execute.",
            },
            "script": {
                "type": "string",
                "description": (
                    "Python code, file path, or URL. Triggers Python mode. "
                    "Mutually exclusive with 'command'."
                ),
            },
            "dependencies": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Pip packages to install for Python mode. "
                    "Common: ['transformers', 'trl', 'torch', 'datasets', 'trackio']."
                ),
            },
            "python": {
                "type": "string",
                "description": "Python version for UV (e.g. '3.11', '3.12').",
            },
            "script_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extra CLI args passed to the script.",
            },
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Docker command. Mutually exclusive with 'script'.",
            },
            "image": {
                "type": "string",
                "description": "Docker image. Auto-selected if not provided.",
            },
            "hardware_flavor": {
                "type": "string",
                "description": (
                    "Hardware tier. "
                    f"CPU: {CPU_FLAVORS}. GPU: {GPU_FLAVORS}."
                ),
            },
            "timeout": {
                "type": "string",
                "description": (
                    "Max job runtime. MUST be >2h for training. "
                    "1-3B: 3-4h, 7-13B: 6-8h, 30B+: 12-24h. Default: '30m'."
                ),
            },
            "env": {
                "type": "object",
                "description": "Environment variables dict. HF_TOKEN is auto-included.",
                "additionalProperties": {"type": "string"},
            },
            "secrets": {
                "type": "object",
                "description": "Secret env vars (HF_TOKEN auto-included).",
                "additionalProperties": {"type": "string"},
            },
            "trackio_space_id": {
                "type": "string",
                "description": (
                    "HF Space hosting trackio dashboard "
                    "(e.g. '<username>/ml-intern-<8char>')."
                ),
            },
            "trackio_project": {
                "type": "string",
                "description": "Trackio project name.",
            },
            "namespace": {
                "type": "string",
                "description": "Namespace to run under (default: caller's account).",
            },
            "job_id": {
                "type": "string",
                "description": "Job ID (for logs, inspect, cancel).",
            },
            "scheduled_job_id": {
                "type": "string",
                "description": "Scheduled job ID.",
            },
            "schedule": {
                "type": "string",
                "description": "Cron or preset (@hourly, @daily, @weekly, @monthly). Required for scheduled run.",
            },
            "all": {
                "type": "boolean",
                "description": "Show all jobs (default: only running).",
            },
        },
        "required": ["operation"],
    }

    def __init__(self) -> None:
        super().__init__()
        self._hf_token: str | None = None
        self._api: HfApi | None = None
        self._namespace: str | None = None

    def _ensure_api(self, token: str, namespace: str | None = None) -> HfApi:
        self._hf_token = token
        self._namespace = namespace
        if self._api is None or self._hf_token != token:
            self._api = HfApi(token=token)
        return self._api

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        import os
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return ToolOutput(success=False, result=None, error="HF_TOKEN environment variable is required")

        operation = getattr(input_data, "operation", None)
        if not operation:
            return ToolOutput(success=False, result=None, error="operation is required")

        namespace = getattr(input_data, "namespace", None)
        api = self._ensure_api(hf_token, namespace)

        params = {}
        for attr in ("script", "command", "image", "hardware_flavor", "timeout",
                     "job_id", "scheduled_job_id", "schedule", "namespace",
                     "dependencies", "python", "script_args", "env", "secrets",
                     "trackio_space_id", "trackio_project", "all"):
            val = getattr(input_data, attr, None)
            if val is not None:
                params[attr] = val

        try:
            result = await self._route(api, operation, params, hf_token)
            return ToolOutput(success=result.get("isError", False) is False, result=result.get("formatted"), error=None)
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error executing {operation}: {e}")

    async def _route(self, api: HfApi, operation: str, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        ops = {
            "run": self._run_job,
            "ps": self._list_jobs,
            "logs": self._get_logs,
            "inspect": self._inspect_job,
            "cancel": self._cancel_job,
            "scheduled run": self._scheduled_run,
            "scheduled ps": self._list_scheduled_jobs,
            "scheduled inspect": self._inspect_scheduled_job,
            "scheduled delete": self._delete_scheduled_job,
            "scheduled suspend": self._suspend_scheduled_job,
            "scheduled resume": self._resume_scheduled_job,
        }
        handler = ops.get(operation)
        if not handler:
            return {"formatted": f"Unknown operation: {operation}", "isError": True}
        return await handler(api, args, hf_token)

    async def _run_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        script = args.get("script")
        command = args.get("command")

        if script and command:
            return {"formatted": "script and command are mutually exclusive.", "isError": True}
        if not script and not command:
            return {"formatted": "Either script or command is required.", "isError": True}

        if script:
            deps = _ensure_hf_transfer_dependency(args.get("dependencies"))
            resolved = _resolve_uv_command(
                script=script,
                with_deps=deps,
                python=args.get("python"),
                script_args=args.get("script_args"),
            )
            image = args.get("image", UV_DEFAULT_IMAGE)
            job_type = "Python"
        else:
            resolved = list(command or [])
            image = args.get("image", "python:3.12")
            job_type = "Docker"

        env_dict = dict(_DEFAULT_ENV)
        env_dict.update(args.get("env") or {})

        trackio_space_id = args.get("trackio_space_id")
        trackio_project = args.get("trackio_project")
        if trackio_space_id:
            env_dict["TRACKIO_SPACE_ID"] = trackio_space_id
        if trackio_project:
            env_dict["TRACKIO_PROJECT"] = trackio_project

        secrets = dict(args.get("secrets") or {})
        secrets["HF_TOKEN"] = hf_token
        secrets["HUGGINGFACE_HUB_TOKEN"] = hf_token

        flavor = args.get("hardware_flavor", "cpu-basic")
        timeout = args.get("timeout", "30m")

        async def _async_call(f, *a, **kw):
            return await asyncio.to_thread(f, *a, **kw)

        try:
            job = await _async_call(
                api.run_job,
                image=image,
                command=resolved,
                env=env_dict,
                secrets=secrets,
                flavor=flavor,
                timeout=timeout,
                namespace=self._namespace,
            )
        except HfHubHTTPError as e:
            if _is_billing_error(str(e)):
                return {
                    "formatted": (
                        f"HF Jobs rejected: namespace `{self._namespace}` has no available credits. "
                        "Add credits at https://huggingface.co/settings/billing then re-run."
                    ),
                    "isError": True,
                }
            raise

        final_status, all_logs = await self._wait_for_job_completion(api, job.id)
        filtered_logs = _filter_uv_install_output(all_logs)
        log_text = _strip_ansi("\n".join(filtered_logs)) if filtered_logs else "(no logs)"

        return {
            "formatted": (
                f"{job_type} job completed!\n\n"
                f"**Job ID:** {job.id}\n"
                f"**Final Status:** {final_status}\n"
                f"**View at:** {job.url}\n\n"
                f"**Logs:**\n```\n{log_text}\n```"
            ),
            "isError": final_status not in ("COMPLETED",),
        }

    async def _wait_for_job_completion(self, api: HfApi, job_id: str) -> tuple[str, list[str]]:
        all_logs: list[str] = []
        terminal_states = {"COMPLETED", "FAILED", "CANCELED", "ERROR"}
        max_retries = 100
        retry_delay = 5

        async def _acall(f, *a, **kw):
            return await asyncio.to_thread(f, *a, **kw)

        for _ in range(max_retries):
            try:
                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_running_loop()

                def producer():
                    try:
                        gen = api.fetch_job_logs(job_id=job_id, namespace=self._namespace)
                        for line in gen:
                            loop.call_soon_threadsafe(queue.put_nowait, line)
                        loop.call_soon_threadsafe(queue.put_nowait, None)
                    except Exception as e:
                        loop.call_soon_threadsafe(queue.put_nowait, e)

                await loop.run_in_executor(None, producer)

                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item
                    all_logs.append(item)
                break

            except (
                ConnectionError, TimeoutError, OSError,
                http.client.IncompleteRead,
                httpx.RemoteProtocolError, httpx.ReadError,
                HfHubHTTPError,
            ):
                try:
                    info = await _acall(api.inspect_job, job_id=job_id, namespace=self._namespace)
                    if info.status.stage in terminal_states:
                        break
                except Exception:
                    pass
                await asyncio.sleep(retry_delay)

        final_status = "UNKNOWN"
        for _ in range(6):
            info = await _acall(api.inspect_job, job_id=job_id, namespace=self._namespace)
            final_status = info.status.stage
            if final_status in terminal_states:
                break
            await asyncio.sleep(2.5)

        return final_status, all_logs

    async def _list_jobs(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        jobs = await asyncio.to_thread(api.list_jobs, namespace=self._namespace)
        if not args.get("all"):
            jobs = [j for j in jobs if j.status.stage == "RUNNING"]
        if args.get("status"):
            s = args["status"].upper()
            jobs = [j for j in jobs if s in j.status.stage]
        if not jobs:
            return {"formatted": "No jobs found."}
        lines = [f"**Jobs ({len(jobs)}):**\n"]
        for j in jobs:
            lines.append(f"- **{j.id}** — {j.status.stage} — {j.flavor}")
        return {"formatted": "\n".join(lines)}

    async def _get_logs(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        job_id = args.get("job_id")
        if not job_id:
            return {"formatted": "job_id is required", "isError": True}
        gen = api.fetch_job_logs(job_id=job_id, namespace=self._namespace)
        logs = await asyncio.to_thread(list, gen)
        if not logs:
            return {"formatted": f"No logs for {job_id}"}
        return {"formatted": f"**Logs for {job_id}:**\n```\n{_strip_ansi('\n'.join(logs))}\n```"}

    async def _inspect_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        job_id = args.get("job_id")
        if not job_id:
            return {"formatted": "job_id is required", "isError": True}
        job = await asyncio.to_thread(api.inspect_job, job_id=job_id, namespace=self._namespace)
        d = _job_info_to_dict(job)
        return {"formatted": f"**Job Details:**\n```json\n{json.dumps(d, indent=2)}\n```"}

    async def _cancel_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        job_id = args.get("job_id")
        if not job_id:
            return {"formatted": "job_id is required", "isError": True}
        await asyncio.to_thread(api.cancel_job, job_id=job_id, namespace=self._namespace)
        return {"formatted": f"✓ Job {job_id} cancelled."}

    async def _scheduled_run(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        script = args.get("script")
        command = args.get("command")
        schedule = args.get("schedule")
        if not schedule:
            return {"formatted": "schedule is required for scheduled jobs", "isError": True}
        if script and command:
            return {"formatted": "script and command are mutually exclusive.", "isError": True}
        if not script and not command:
            return {"formatted": "Either script or command is required.", "isError": True}

        if script:
            deps = _ensure_hf_transfer_dependency(args.get("dependencies"))
            resolved = _resolve_uv_command(script, with_deps=deps, python=args.get("python"), script_args=args.get("script_args"))
            image = args.get("image", UV_DEFAULT_IMAGE)
        else:
            resolved = list(command or [])
            image = args.get("image", "python:3.12")

        env_dict = dict(_DEFAULT_ENV)
        env_dict.update(args.get("env") or {})

        secrets = dict(args.get("secrets") or {})
        secrets["HF_TOKEN"] = hf_token

        sj = await asyncio.to_thread(
            api.create_scheduled_job,
            image=image,
            command=resolved,
            schedule=schedule,
            env=env_dict,
            secrets=secrets,
            flavor=args.get("hardware_flavor", "cpu-basic"),
            timeout=args.get("timeout", "30m"),
            namespace=self._namespace,
        )
        d = _scheduled_job_info_to_dict(sj)
        return {
            "formatted": (
                f"✓ Scheduled job created!\n"
                f"**ID:** {d['id']}\n"
                f"**Schedule:** {d['schedule']}\n"
                f"**Next Run:** {d.get('nextRun', 'N/A')}"
            ),
        }

    async def _list_scheduled_jobs(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        jobs = await asyncio.to_thread(api.list_scheduled_jobs, namespace=self._namespace)
        if not args.get("all"):
            jobs = [j for j in jobs if not j.suspend]
        if not jobs:
            return {"formatted": "No scheduled jobs found."}
        lines = [f"**Scheduled Jobs ({len(jobs)}):**\n"]
        for j in jobs:
            lines.append(f"- **{j.id}** — cron: {j.schedule} — {'suspended' if j.suspend else 'active'}")
        return {"formatted": "\n".join(lines)}

    async def _inspect_scheduled_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        sj_id = args.get("scheduled_job_id")
        if not sj_id:
            return {"formatted": "scheduled_job_id is required", "isError": True}
        sj = await asyncio.to_thread(api.inspect_scheduled_job, scheduled_job_id=sj_id, namespace=self._namespace)
        d = _scheduled_job_info_to_dict(sj)
        return {"formatted": f"**Scheduled Job:**\n```json\n{json.dumps(d, indent=2)}\n```"}

    async def _delete_scheduled_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        sj_id = args.get("scheduled_job_id")
        if not sj_id:
            return {"formatted": "scheduled_job_id is required", "isError": True}
        await asyncio.to_thread(api.delete_scheduled_job, scheduled_job_id=sj_id, namespace=self._namespace)
        return {"formatted": f"✓ Scheduled job {sj_id} deleted."}

    async def _suspend_scheduled_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        sj_id = args.get("scheduled_job_id")
        if not sj_id:
            return {"formatted": "scheduled_job_id is required", "isError": True}
        await asyncio.to_thread(api.suspend_scheduled_job, scheduled_job_id=sj_id, namespace=self._namespace)
        return {"formatted": f"✓ Scheduled job {sj_id} suspended."}

    async def _resume_scheduled_job(self, api: HfApi, args: dict[str, Any], hf_token: str) -> dict[str, Any]:
        sj_id = args.get("scheduled_job_id")
        if not sj_id:
            return {"formatted": "scheduled_job_id is required", "isError": True}
        await asyncio.to_thread(api.resume_scheduled_job, scheduled_job_id=sj_id, namespace=self._namespace)
        return {"formatted": f"✓ Scheduled job {sj_id} resumed."}
