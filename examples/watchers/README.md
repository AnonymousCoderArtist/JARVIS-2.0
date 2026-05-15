# JARVIS Watcher Examples

This directory contains example watchers — background plugins that run continuously in JARVIS.

## Quick Start

Watchers are discovered from `.jarvis/watchers/` (project) or `~/.jarvis/watchers/` (global).
Each watcher is a Python package (directory with `__init__.py`) containing a class that extends `BaseWatcher`.

## Examples

| Directory | Description |
|-----------|-------------|
| `git_status_watcher/` | Monitors git repository status — branch, uncommitted changes, ahead/behind remote |
| `disk_monitor/` | Watches disk usage and alerts when thresholds are exceeded |
| `dependency_watcher/` | Checks for outdated dependencies and known security vulnerabilities |
| `log_tail_watcher/` | Tails a log file and notifies on error patterns |

## See Also

- [Watchers Documentation](../../docs/watchers.md) — full API reference and patterns
- [BaseWatcher](../../core/watchers/base.py) — the base class all watchers extend
- [WatcherManager](../../core/watchers/manager.py) — discovery and lifecycle management
