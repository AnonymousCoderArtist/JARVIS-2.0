"""Crystallize successful tool trajectories into reusable skills.

This is inspired by GenericAgent's "self-evolving" approach:
- run a task with tools
- persist the execution path as a skill/SOP
- reuse later via explicit activation or discovery
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.tools.skill_manage_tool import create_skill_markdown, get_skill_dir


@dataclass(frozen=True)
class CrystallizedSkill:
    name: str
    path: str
    created: bool


def _slugify(text: str, max_len: int = 60) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = t.strip("-")
    if not t:
        return "task"
    return t[:max_len].strip("-")


def _summarize_value(val: Any, max_len: int = 200) -> str:
    if val is None:
        return ""
    s = str(val)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


class SkillCrystallizer:
    """Turn a per-task execution trace into an `SKILL.md`."""

    def __init__(self, index_path: Path | None = None) -> None:
        # A lightweight index that maps keywords -> auto skills.
        # Kept in the project when possible, otherwise in the global skill dir.
        self.index_path = index_path

    def crystallize(
        self,
        *,
        user_input: str,
        final_response: str,
        execution_trace: list[dict[str, Any]],
        success: bool,
        min_steps: int = 3,
    ) -> CrystallizedSkill | None:
        if not success:
            return None
        if not execution_trace or len(execution_trace) < min_steps:
            return None

        # Name: stable, human-invocable, and searchable.
        base = _slugify(user_input)
        today = datetime.now().strftime("%Y%m%d")
        skill_name = f"auto-{base}-{today}"

        skill_dir = get_skill_dir() / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        tools_used = [str(s.get("tool", "")) for s in execution_trace if s.get("tool")]
        tools_uniq = [t for i, t in enumerate(tools_used) if t and t not in tools_used[:i]]

        failures = [s for s in execution_trace if s.get("success") is False and s.get("tool")]

        procedure_lines: list[str] = []
        for i, step in enumerate(execution_trace, 1):
            tool = str(step.get("tool", ""))
            if not tool:
                continue
            args = step.get("args")
            arg_str = _summarize_value(args, 220)
            ok = bool(step.get("success"))
            res = _summarize_value(step.get("result"), 220)
            err = _summarize_value(step.get("error"), 180)
            status = "ok" if ok else "failed"

            line = f"{i}. Use `{tool}` ({status})"
            if arg_str:
                line += f" with args: {arg_str}"
            if ok and res:
                line += f" → result: {res}"
            if (not ok) and err:
                line += f" → error: {err}"
            procedure_lines.append(line)

        pitfalls = ""
        if failures:
            pit = []
            for f in failures[:5]:
                pit.append(
                    f"- `{f.get('tool')}` failed: {_summarize_value(f.get('error') or f.get('result'), 220)}"
                )
            pitfalls = "\n".join(pit)

        verification = "\n".join(
            [
                "- Re-run the task on a small sample input first.",
                "- Confirm no tool failures occurred and outputs match expectations.",
                "- If this touches files, verify diffs and run relevant tests.",
            ]
        )

        skill_md = create_skill_markdown(
            name=skill_name,
            description=f"Auto-crystallized from a successful run. Tools: {', '.join(tools_uniq) if tools_uniq else 'N/A'}",
            when_to_use=f"When you need to do something similar to: {user_input}",
            when_not_to_use="When the environment/tools differ materially, or the task is one-off and not worth standardizing.",
            procedure="\n".join(procedure_lines),
            pitfalls=pitfalls,
            verification=verification,
            category="auto",
            tags=[*tools_uniq[:8]],
        )

        created = not skill_file.exists()
        skill_file.write_text(skill_md, encoding="utf-8")

        self._update_index(
            skill_name=skill_name,
            user_input=user_input,
            tools=tools_uniq,
            response=_summarize_value(final_response, 240),
        )

        return CrystallizedSkill(name=skill_name, path=str(skill_file), created=created)

    def _update_index(self, *, skill_name: str, user_input: str, tools: list[str], response: str) -> None:
        # Prefer project-local `.jarvis/skill_index.md` when available.
        idx = self.index_path
        if idx is None:
            # If the repo has `.jarvis/`, keep the index there; else use the global skills dir.
            cwd = Path.cwd()
            jarvis_dir = None
            for parent in [cwd, *cwd.parents]:
                if (parent / ".jarvis").exists():
                    jarvis_dir = parent / ".jarvis"
                    break
            idx = (jarvis_dir / "skill_index.md") if jarvis_dir else (get_skill_dir() / "skill_index.md")

        idx.parent.mkdir(parents=True, exist_ok=True)
        if not idx.exists():
            idx.write_text("# Skill Index (auto)\n\n", encoding="utf-8")

        line = f"- `{skill_name}` — {user_input} | tools: {', '.join(tools) if tools else 'N/A'} | last: {response}\n"
        # Prepend for recency.
        old = idx.read_text(encoding="utf-8")
        if line in old:
            return
        idx.write_text(old + line if old.endswith("\n") else old + "\n" + line, encoding="utf-8")

