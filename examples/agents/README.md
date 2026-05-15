# JARVIS Agent Examples

This directory contains example custom agent definitions. Place these in `.jarvis/agents/` (project) or `~/.jarvis/agents/` (global) to use them.

## Examples

| File | Description |
|------|-------------|
| `code_reviewer.py` | Read-only code reviewer — focuses on security, bugs, and style |
| `researcher.py` | Deep research subagent with web search and documentation tools |
| `implementer.py` | Full-stack implementation agent with all write/edit/bash tools |
| `test_writer.py` | Specialized agent for writing and running tests |
| `security_auditor.py` | Security-focused auditor that scans for vulnerabilities |
| `doc_writer.py` | Documentation writer with read-only access to codebase |

## See Also

- [Custom Agents Documentation](../../docs/custom-agents.md) — full API reference
- [AgentDefinition](../../core/agents/agent_definition.py) — the dataclass backing custom agents
- [AgentType](../../core/agents/profiles.py) — AGENT vs SUBAGENT distinction
