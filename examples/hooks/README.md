# JARVIS Hook & Event Examples

This directory contains example lifecycle hooks and event handlers. These demonstrate how to intercept, modify, and observe JARVIS execution at various stages.

## Hook Examples

| File | Stage | What it does |
|------|-------|-------------|
| `safety_gate.py` | `BEFORE_TOOL_CALL` | Blocks dangerous commands (rm -rf, sudo, curl | bash) |
| `tool_rate_limiter.py` | `BEFORE_TOOL_CALL` | Rate-limits expensive tool calls to prevent abuse |
| `prompt_injector.py` | `BEFORE_SYSTEM_PROMPT` | Injects additional context into the system prompt |
| `tool_logger.py` | `AFTER_TOOL_CALL` | Logs every tool call with duration and result summary |
| `turn_counter.py` | `BEFORE_TURN` / `AFTER_TURN` | Tracks and limits turn count with warnings |
| `session_guard.py` | `BEFORE_SESSION_START` | Validates session configuration before starting |

## Event Handler Examples

| File | Events | What it does |
|------|--------|-------------|
| `event_logger.py` | All events | Comprehensive event logger (also in `../extensions/`) |
| `progress_tracker.py` | `ToolCallStarted`, `ToolCallEnded` | Tracks tool call durations and success rates |
| `error_monitor.py` | `AgentError`, `ToolCallError` | Collects and summarizes errors at session end |

## See Also

- [Hooks Documentation](../../docs/HOOKS.md) — full API reference for EventBus and HookRegistry
- [HookRegistry](../../core/events/hooks.py) — 16 lifecycle stages, HookContext, HookResult
- [EventBus](../../core/events/bus.py) — pub/sub with priority ordering and polymorphic dispatch
- [Event Types](../../core/events/types.py) — 24 event type definitions
