# Watchers

Watchers are background plugins that run continuously in JARVIS. They are automatically discovered from `.jarvis/watchers/` and run on their defined schedule.

## Quick Start

Create `.jarvis/watchers/my_watcher/__init__.py`:

```python
from core.watchers.base import BaseWatcher

class MyWatcher(BaseWatcher):
    name = "my_watcher"
    description = "My custom watcher"

    def __init__(self):
        super().__init__(interval=60)  # Run every 60 seconds

    async def watch(self):
        # Your logic here - this is the ONLY required method
        data = {"status": "ok"}
        self.update_cop(data)
```

That's it! JARVIS will automatically discover and run your watcher.

## The Only Rule: `watch()`

The `watch()` method is the **only required implementation**. Everything else is optional - customize as you need.

```python
async def watch(self):
    """
    This runs every `interval` seconds.
    Implement YOUR logic here.
    """
    pass
```

## Advanced Patterns & Best Practices

To build a robust watcher like the `world_monitor`, follow these "important" patterns:

### 1. COP (Common Operational Picture) - [REQUIRED]
The COP is the **primary mechanism** for persisting state (`.jarvis/status/<Name>.cop.jsonl`). Use it to store any data that other agents might need to know about. 
- `update_cop(data)`: Appends a new timestamped entry.
- `get_cop()`: Retrieves the last 10 entries.

### 2. UI Notifications (Assistant Events) - [OPTIONAL]
Watchers are background engines, but they can optionally alert the user via the JARVIS UI using `notify()`.

```python
async def watch(self):
    data = await self.fetch()
    # Always persist state for agents
    self.update_cop(data)
    
    # Optionally notify the user for important events
    if data.get("is_critical"):
        await self.notify(
            title="Critical Alert", 
            message="Data threshold exceeded", 
            level="warning"
        )
```

This method handles:
- Formatting with emojis (🔵 info, 🟡 warning, 🔴 error).
- Sending an `AssistantEvent` to the UI with `is_heartbeat=True`.
- Logging the event automatically.

### 3. Modular Architecture
For complex watchers, separate your logic into:
- `client.py`: API communication, session handling, and authentication.
- `extractors.py`: Pure functions to parse raw API data into clean items.
- `registry.py`: Centralized endpoint management and priority levels.

### 4. Full Implementation Example
Here is a complete, modular watcher that utilizes all the best practices:

```python
import aiohttp
from core.watchers.base import BaseWatcher

class SystemMonitorWatcher(BaseWatcher):
    name = "system_monitor"
    description = "Monitors external system health"

    def __init__(self):
        super().__init__(interval=300) # Run every 5 minutes
        config = self.load_config()
        self.api_key = config.get("api_key")

    async def watch(self):
        # 1. Fetch data
        data = await self._fetch_system_status()
        
        # 2. REQUIRED: Update COP for agents
        self.update_cop(data)
        
        # 3. OPTIONAL: Notify user on failure
        if data.get("status") == "down":
            await self.notify(
                title="System Down", 
                message=f"System {data['system_id']} is unresponsive!", 
                level="error"
            )

    async def _fetch_system_status(self):
        # Implementation details...
        return {"status": "down", "system_id": "main_server"}
```

This pattern ensures that agents always have the latest data in the COP while providing you with critical alerts only when needed.

### 4. Efficient Polling
Don't poll everything at once. Use a sliding window or priority-based cycles:

```python
# In your __init__
self._cycle_index = 0
self.high_priority = ["critical_endpoint", "alert_feed"]

# In watch()
endpoints = list(all_endpoints.keys())
subset = set(self.high_priority)
for _ in range(3): # Add 3 more from the sliding window
    subset.add(endpoints[self._cycle_index % len(endpoints)])
    self._cycle_index += 1
```

### 5. Change Detection (Hashing)
Avoid spamming notifications by hashing the results and only notifying when the hash changes.

```python
import hashlib
import json

item_hash = hashlib.md5(json.dumps(items, sort_keys=True).encode()).hexdigest()
if self._last_hash != item_hash:
    self._last_hash = item_hash
    await self.notify("New Update", items[0]["text"])
```

## BaseWatcher Reference

### Required

| Attribute | Description |
|-----------|-------------|
| `name` | Unique name for your watcher (used for config lookup) |
| `watch()` | **Implement this** - your main logic |

### Optional Initialization

| Method | Description |
|--------|-------------|
| `__init__(interval=60)` | Set polling interval (default: 60 seconds) |

### Utilities (Use as Needed)

| Method | Description |
|--------|-------------|
| `load_config()` | Get your config from `settings.json` under `watcher.<name>` |
| `enabled` | Property - check if enabled in config (default: True) |
| `update_cop(data)` | Store data in `.jarvis/status/<Name>.cop.jsonl` |
| `get_cop()` | Read last 10 entries from COP |
| `set_event_queue(queue)` | Connect to JARVIS UI |

### Lifecycle (Override as Needed)

| Method | Description |
|--------|-------------|
| `start()` | Runs once when watcher starts |
| `stop()` | Runs when watcher stops (cleanup) |

## Configuration

Add your watcher's config to `.jarvis/settings.json`:

```json
"watcher": {
    "my_watcher": {
        "enabled": true,
        "any_setting": "any_value"
    }
}
```