"""Dataset inspection tool — comprehensive dataset analysis in one call.

Ported from huggingface/ml-intern agent/tools/dataset_tools.py.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, cast

import httpx

from jarvis.api import BaseTool, ToolInput, ToolOutput

BASE_URL = "https://datasets-server.huggingface.co"
MAX_SAMPLE_VALUE_LEN = 150


def _get_headers(token: str | None = None) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def _inspect_dataset(
    dataset: str,
    config: str | None = None,
    split: str | None = None,
    sample_rows: int = 3,
    hf_token: str | None = None,
) -> dict[str, Any]:
    headers = _get_headers(hf_token)
    output_parts: list[str] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        # Phase 1: parallel calls
        is_valid_task = client.get(f"{BASE_URL}/is-valid", params={"dataset": dataset})
        splits_task = client.get(f"{BASE_URL}/splits", params={"dataset": dataset})
        parquet_task = client.get(f"{BASE_URL}/parquet", params={"dataset": dataset})

        results = await asyncio.gather(is_valid_task, splits_task, parquet_task, return_exceptions=True)

        # Process is-valid
        if not isinstance(results[0], Exception):
            try:
                data = cast(httpx.Response, results[0]).json()
                available = [k for k in ["viewer", "preview", "search", "filter", "statistics"] if data.get(k)]
                if available:
                    output_parts.append(f"## Status\nValid ({', '.join(available)})")
                else:
                    output_parts.append("## Status\nDataset may have issues")
            except Exception as e:
                errors.append(f"is-valid: {e}")

        # Process splits
        configs: list[dict[str, Any]] = []
        if not isinstance(results[1], Exception):
            try:
                splits_data = cast(httpx.Response, results[1]).json()
                cfg_map: dict[str, dict[str, Any]] = {}
                for s in splits_data.get("splits", []):
                    cfg = s.get("config", "default")
                    if cfg not in cfg_map:
                        cfg_map[cfg] = {"name": cfg, "splits": []}
                    cfg_map[cfg]["splits"].append(s.get("split"))
                configs = list(cfg_map.values())
                if not config:
                    config = configs[0]["name"] if configs else "default"
                if not split:
                    split = configs[0]["splits"][0] if configs else "train"
                # Format structure
                lines = ["## Structure (configs & splits)", "| Config | Split |", "|--------|-------|"]
                count = 0
                for cfg in configs:
                    for sname in cfg["splits"]:
                        if count >= 10:
                            break
                        lines.append(f"| {cfg['name']} | {sname} |")
                        count += 1
                output_parts.append("\n".join(lines))
            except Exception as e:
                errors.append(f"splits: {e}")

        if not config:
            config = "default"
        if not split:
            split = "train"

        # Parquet info
        parquet_section = None
        if not isinstance(results[2], Exception):
            try:
                pdata = cast(httpx.Response, results[2]).json()
                pfiles = pdata.get("parquet_files", [])
                if pfiles:
                    groups: dict[str, dict] = {}
                    for f in pfiles:
                        key = f"{f.get('config', 'default')}/{f.get('split', 'train')}"
                        if key not in groups:
                            groups[key] = {"count": 0, "size": 0}
                        size = f.get("size") or 0
                        if not isinstance(size, (int, float)):
                            size = 0
                        groups[key]["count"] += 1
                        groups[key]["size"] += int(size)
                    lines = ["## Files (Parquet)"]
                    for key, info in list(groups.items())[:10]:
                        size_mb = info["size"] / (1024 * 1024)
                        lines.append(f"- {key}: {info['count']} file(s) ({size_mb:.1f} MB)")
                    parquet_section = "\n".join(lines)
            except Exception:
                pass

        # Phase 2: content
        info_task = client.get(f"{BASE_URL}/info", params={"dataset": dataset, "config": config})
        rows_task = client.get(f"{BASE_URL}/first-rows", params={"dataset": dataset, "config": config, "split": split}, timeout=30)

        content_results = await asyncio.gather(info_task, rows_task, return_exceptions=True)

        # Schema
        if not isinstance(content_results[0], Exception):
            try:
                info_data = cast(httpx.Response, content_results[0]).json()
                features = info_data.get("dataset_info", {}).get("features", {})
                lines = [f"## Schema ({config})", "| Column | Type |", "|--------|------|"]
                for col_name, col_info in features.items():
                    dtype = col_info.get("dtype") or col_info.get("_type", "unknown")
                    if col_info.get("_type") == "ClassLabel":
                        names = col_info.get("names", [])
                        dtype = f"ClassLabel ({len(names)} classes)"
                    lines.append(f"| {col_name} | {dtype} |")
                output_parts.append("\n".join(lines))
            except Exception as e:
                errors.append(f"info: {e}")

        # Sample rows
        if not isinstance(content_results[1], Exception):
            try:
                rows_data = cast(httpx.Response, content_results[1]).json()
                rows = rows_data.get("rows", [])[:sample_rows]
                lines = [f"## Sample Rows ({config}/{split})"]
                for i, row_wrapper in enumerate(rows, 1):
                    row = row_wrapper.get("row", {})
                    lines.append(f"**Row {i}:**")
                    for key, val in row.items():
                        val_str = str(val)
                        if len(val_str) > MAX_SAMPLE_VALUE_LEN:
                            val_str = val_str[:MAX_SAMPLE_VALUE_LEN] + "..."
                        lines.append(f"- {key}: {val_str}")
                output_parts.append("\n".join(lines))
            except Exception as e:
                errors.append(f"rows: {e}")

        if parquet_section:
            output_parts.append(parquet_section)

    formatted = f"# {dataset}\n\n" + "\n\n".join(output_parts)
    if errors:
        formatted += f"\n\n**Warnings:** {'; '.join(errors)}"

    return {"formatted": formatted, "isError": len(output_parts) == 0}


class HfInspectDatasetTool(BaseTool):
    name = "hf_inspect_dataset"
    description = (
        "Inspect a HF dataset in one call: status, configs/splits, schema, sample rows, parquet info.\n\n"
        "REQUIRED before any training job to verify dataset format matches training method:\n"
        "  SFT: needs 'messages', 'text', or 'prompt'/'completion'\n"
        "  DPO: needs 'prompt', 'chosen', 'rejected'\n"
        "  GRPO: needs 'prompt'\n"
        "All datasets used for training have to be in conversational ChatML format to be compatible with HF libraries.\n"
        "Training will fail with KeyError if columns don't match.\n\n"
        "Also use to get example datapoints, understand column names, data types, and available splits before writing any data loading code. "
        "Supports private/gated datasets when HF_TOKEN is set."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dataset": {
                "type": "string",
                "description": "Dataset ID in 'org/name' format (e.g., 'stanfordnlp/imdb')",
            },
            "config": {
                "type": "string",
                "description": "Config/subset name. Auto-detected if not specified.",
            },
            "split": {
                "type": "string",
                "description": "Split for sample rows. Auto-detected if not specified.",
            },
            "sample_rows": {
                "type": "integer",
                "description": "Number of sample rows to show (default: 3, max: 10)",
                "default": 3,
            },
        },
        "required": ["dataset"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        dataset = input_data.query or ""
        config = getattr(input_data, "config", None)
        split = getattr(input_data, "split", None)
        sample_rows = min(getattr(input_data, "sample_rows", 3) or 3, 10)

        if not dataset:
            return ToolOutput(success=False, result=None, error="dataset is required")

        hf_token = os.environ.get("HF_TOKEN")
        try:
            result = await _inspect_dataset(
                dataset=dataset,
                config=config,
                split=split,
                sample_rows=sample_rows,
                hf_token=hf_token,
            )
            return ToolOutput(success=not result.get("isError", False), result=result["formatted"])
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error inspecting dataset: {e}")
