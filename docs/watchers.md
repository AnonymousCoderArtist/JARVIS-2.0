# Watchers

JARVIS uses a tiered monitoring system that allows for background awareness and autonomous management. Watchers are discovered automatically from `.jarvis/watchers/`.

## Tiered Architecture

| Tier | Type | Power | Description |
|------|------|-------|-------------|
| **Tier 1** | **Passive** | Script | Non-AI scripts that poll data (e.g., API, local file) and log historical intelligence to the COP. |
| **Tier 2** | **Agentic** | Agent | AI-powered autonomous agents that monitor streams and take proactive actions. |

## Passive Watchers (Tier 1)

Passive watchers are lightweight and designed for 24/7 data polling.

### Directory Structure

Each watcher must have its own directory in `.jarvis/watchers/` with an `__init__.py` file:

```text
.jarvis/watchers/
└── my_watcher/
    ├── __init__.py      <-- JARVIS registers from here
    └── utils.py         # Optional helpers
```

### Creating a Passive Watcher

Create `.jarvis/watchers/system_health/__init__.py`:

```python
import psutil
from core.watchers.base import BaseWatcher

class SystemHealthWatcher(BaseWatcher):
    name = "system_health"
    description = "Monitors local CPU and Memory usage"
    
    def __init__(self):
        # Set poll interval to 30 seconds
        super().__init__(interval=30)

    async def watch(self):
        # Gather data
        stats = {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
        
        # Update the Common Operational Picture (COP)
        # This appends a new timestamped entry to .jarvis/status/SystemHealthWatcher.cop.jsonl
        self.update_cop(stats)
```

## Common Operational Picture (COP)

Watchers store their data in an append-only JSONL format located at `.jarvis/status/`. This allows JARVIS to maintain a full audit trail of environmental intelligence.

### Accessing Watcher Data

JARVIS accesses this data using the `watcher_status` tool, which supports paginated history access:

- `watcher_status(key="SystemHealthWatcher")` (reads recent entries)
- `watcher_status(key="SystemHealthWatcher", offset=0, limit=50)` (paginated access)
- `watcher_status()` (lists all available keys)

## BaseWatcher API

| Method | Description |
|--------|-------------|
| `watch()` | **Required.** The async method that runs every `interval`. |
| `update_cop(data)` | Appends data to `ClassName.cop.jsonl` with a timestamp. |
| `get_cop()` | Reads the most recent entries from the JSONL log. |
| `notify(title, message)` | Sends a system toast notification with full message support. |
| `interval` | The time in seconds between `watch()` calls. |

## Watcher Agents (Tier 2)

*Coming soon.* Watcher agents will provide fully autonomous capabilities using `AsyncAgentManager`.
