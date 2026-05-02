#!/usr/bin/env python
"""Test skill system imports and basic functionality."""

import sys

def test_trace_collector():
    from core.skills.trace_collector import TraceCollector, SkillTrace, get_trace_collector
    print("Trace collector OK")
    tc = get_trace_collector()
    trace = SkillTrace(
        skill_name="test",
        timestamp=0.0,
        input="hello",
        output="world",
        metrics={"latency": 0.1},
        success=True
    )
    tc.record_trace(trace)
    count = tc.get_trace_count("test")
    print(f"  - Recorded trace, count: {count}")
    return True

def test_skill_commands():
    from core.skills.commands import SkillCommands
    print("SkillCommands OK")
    return True

def test_skill_manager():
    from core.skills.manager import SkillManager
    m = SkillManager()
    print("SkillManager OK, skills:", list(m.get_builtin_skills().keys()))
    return True

def main():
    tests = [
        ("trace_collector", test_trace_collector),
        ("skill_commands", test_skill_commands),
        ("skill_manager", test_skill_manager),
    ]
    
    passed = 0
    failed = 0
    
    for name, test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAILED {name}: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())