"""Modular WorldMonitor Watcher - Geopolitical Awareness Engine"""

import hashlib
import json
import logging
import os
import aiohttp
import asyncio
from pathlib import Path
import io
import sys

from jarvis.core.watchers.base import BaseWatcher
from .client import WorldMonitorClient
from .extractors import ContentExtractors
from .registry import EndpointRegistry

# Suppress ALL terminal output for this watcher - prevents干扰 jarvis --cli
class QuietLogger:
    """Null logger that suppresses all output"""
    def __init__(self):
        pass
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass
    def log(self, level, *args, **kwargs): pass

# Create a logger that goes nowhere
logger = QuietLogger()


class WorldMonitorWatcher(BaseWatcher):
    """
    Monitors geopolitical data from worldmonitor.app.
    
    Config (in settings.json):
        "watcher": {
            "world_monitor": {
                "enabled": true,
                "telegram": {
                    "enabled": true,
                    "bot_token": "...",
                    "chat_id": "..."
                }
            }
        }
    """
    name = "world_monitor"
    description = "Geopolitical monitoring from worldmonitor.app"
    
    def __init__(self):
        super().__init__(interval=60)
        
        self.client = WorldMonitorClient(
            base_url="https://api.worldmonitor.app",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # Track individual item hashes per endpoint for deduplication
        # Key: endpoint key, Value: set of item hashes already sent
        self._sent_item_hashes = {}
        self._subset_cycle_index = 0
        self._last_update_id = 0
        
        # Load telegram config
        config = self.load_config()
        self._telegram_config = config.get("telegram", {})
        
        # Setup telegram session
        self._tg_session = None
        self._tg_bot_token = self._telegram_config.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
        
        # Handle single or multiple chat_ids
        chat_id_raw = self._telegram_config.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID")
        if isinstance(chat_id_raw, list):
            self._tg_chat_ids = chat_id_raw
        elif chat_id_raw:
            self._tg_chat_ids = [chat_id_raw]
        else:
            self._tg_chat_ids = []
    
    async def start(self):
        """Called when watcher starts. Silently initializes."""
        # Suppress all terminal output - no logger.info or telegram notifications on startup
        # This prevents interference with jarvis --cli
        pass
    
    async def watch(self):
        """Main logic - cycle through Intelligence subsets and detect changes."""
        logger.debug(f"Watcher {self.name} cycle starting.")
        
        # Check for commands if Telegram is configured
        if self._telegram_config.get("enabled") and self._tg_bot_token:
            try:
                await self._poll_telegram_commands()
            except Exception as e:
                logger.error(f"Watcher {self.name} failed to poll Telegram: {e}")

        all_endpoints = EndpointRegistry.INTELLIGENCE
        endpoint_keys = list(all_endpoints.keys())
        high_priority = [k for k in EndpointRegistry.get_high_priority() if k in all_endpoints]
        
        # Process high priority + sliding window
        subset_to_process = set(high_priority)
        for _ in range(5):
            subset_to_process.add(endpoint_keys[self._subset_cycle_index % len(endpoint_keys)])
            self._subset_cycle_index += 1
        
        status_summary = {}
        
        for key in subset_to_process:
            path = all_endpoints.get(key)
            if not path:
                logger.debug(f"Endpoint {key} not found in registry.")
                continue
            
            try:
                # Fetch data (handle external RSS feeds differently)
                if path.startswith("http"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(path, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                data = {"rss_content": content}
                            else:
                                logger.warning(f"RSS fetch {key} failed with status {resp.status}")
                                continue
                else:
                    data = await self.client.fetch(path)
                
                if not data:
                    continue
                
                # Extract content
                items = ContentExtractors.extract(key, data)
                
                # Get previously sent item hashes for this endpoint
                sent_hashes = self._sent_item_hashes.get(key, set())
                
                # Find truly new items by hashing each individual item
                new_items = []
                for item in items:
                    # Create a unique hash for this individual item
                    item_text = item.get("text", "")
                    item_hash = hashlib.md5(item_text.encode()).hexdigest()
                    
                    # Only include if this specific item hasn't been sent before
                    if item_hash not in sent_hashes:
                        new_items.append(item)
                        # Add to sent hashes so we don't send it again
                        sent_hashes.add(item_hash)
                
                # Update the stored hashes for this endpoint
                self._sent_item_hashes[key] = sent_hashes
                
                # Only send if there are new items
                if new_items:
                    # Check urgency - if any new item is urgent, use warning level
                    is_urgent = any(item.get("urgent") for item in new_items)
                    level = "warning" if is_urgent else "info"
                    
                    # Send new items to Telegram (but suppress terminal/CLI output via QuietLogger)
                    for item in new_items[:5]:
                        text = item.get("text", "New data detected")
                        await self._send_telegram(
                            title="",
                            message=text,
                            level=level
                        )
                        # Rate limit: 3 seconds between messages
                        await asyncio.sleep(3)
                
                status_summary[key] = {
                    "latest": items,
                    "total_available": len(items)
                }
            except Exception as e:
                logger.error(f"Watcher {self.name} failed to process {key}: {e}")
        
        if status_summary:
            self.update_cop(status_summary)
            
    async def _poll_telegram_commands(self):
        """Poll for new commands from Telegram using offset."""
        url = f"https://api.telegram.org/bot{self._tg_bot_token}/getUpdates?offset={self._last_update_id + 1}"
        try:
            if self._tg_session is None:
                self._tg_session = aiohttp.ClientSession()
            
            async with self._tg_session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for update in data.get("result", []):
                        current_update_id = update["update_id"]
                        
                        # Process only if it's a new update
                        if current_update_id > self._last_update_id:
                            self._last_update_id = current_update_id
                            
                            message = update.get("message", {})
                            text = message.get("text", "")
                            chat_id = message.get("chat", {}).get("id")
                            
                            if text == "/start":
                                await self._send_telegram("Bot Started", f"WorldMonitor active. Your chat ID is: `{chat_id}`", "info", chat_id=chat_id)
                            elif text == "/id":
                                await self._send_telegram("Chat ID", f"Your current chat ID is: `{chat_id}`", "info", chat_id=chat_id)
                else:
                    error_text = await resp.text()
                    logger.warning(f"Telegram polling status {resp.status}: {error_text}")
        except Exception as e:
            logger.debug(f"Telegram polling failed: {e}")

    async def notify(self, title: str, message: str, level: str = "info"):
        """Override base notify to suppress ALL output - prevents interference with jarvis --cli."""
        # Completely silent - no UI events, no Telegram, no logging
        # Data is still stored in COP via update_cop() for agents to access
        pass
    
    async def _send_telegram(self, title: str, message: str, level: str, chat_id: int = None):
        """Send notification to Telegram, suppressing errors and ignoring Markdown."""
        text = f"{title}\n\n{message}" if title else message
        
        # Use provided chat_id (if command response) or broadcast to all configured IDs
        targets = [chat_id] if chat_id else self._tg_chat_ids
        
        if not targets:
            return

        url = f"https://api.telegram.org/bot{self._tg_bot_token}/sendMessage"
        
        try:
            if self._tg_session is None:
                self._tg_session = aiohttp.ClientSession()
            
            for target in targets:
                try:
                    async with self._tg_session.post(
                        url,
                        json={"chat_id": target, "text": text},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        pass # Silently suppress
                except Exception:
                    continue # Try next target if one fails
        except Exception:
            pass # Silently suppress all errors
    
    async def stop(self):
        """Cleanup when watcher stops."""
        if self._tg_session:
            await self._tg_session.close()
        await self.client.close()