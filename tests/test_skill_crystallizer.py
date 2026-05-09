from __future__ import annotations

from pathlib import Path

from core.learn.skill_crystallizer import SkillCrystallizer


def test_crystallizer_writes_skill(tmp_path: Path, monkeypatch):
    # Force skills directory into tmp for test isolation.
    from core import tools as _tools_mod  # noqa: F401
    from core.tools import skill_manage_tool

    def _fake_get_skill_dir() -> Path:
        d = tmp_path / "skills"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(skill_manage_tool, "get_skill_dir", _fake_get_skill_dir)

    crystallizer = SkillCrystallizer(index_path=tmp_path / "skill_index.md")
    trace = [
        {"tool": "file_read", "args": {"path": "README.md"}, "success": True, "result": "ok", "error": None},
        {"tool": "grep", "args": {"pattern": "foo"}, "success": True, "result": "1 match", "error": None},
        {"tool": "run_tests", "args": {"target": "tests/"}, "success": True, "result": "pass", "error": None},
        {"tool": "edit_file", "args": {"path": "x.py"}, "success": True, "result": "done", "error": None},
        {"tool": "ls", "args": {"path": "."}, "success": True, "result": "files", "error": None},
    ]

    out = crystallizer.crystallize(
        user_input="Update README and run tests",
        final_response="Done",
        execution_trace=trace,
        success=True,
        min_steps=3,
    )

    assert out is not None
    skill_path = Path(out.path)
    assert skill_path.exists()
    assert skill_path.name == "SKILL.md"
    assert "auto-update-readme-and-run-tests" in skill_path.as_posix()

    idx = tmp_path / "skill_index.md"
    assert idx.exists()
    assert "auto-update-readme-and-run-tests" in idx.read_text(encoding="utf-8")

