"""Tests for heartbeat scheduler - nanobot-style two-phase implementation"""

import asyncio
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.agents.heartbeat_scheduler import (
    HeartbeatScheduler,
    parse_interval,
    is_within_active_hours,
    get_heartbeat_file,
    parse_heartbeat_file,
    format_heartbeat_result,
    is_deliverable,
)


class TestParseInterval:
    """Tests for parse_interval function"""
    
    def test_parse_seconds(self):
        assert parse_interval("30s") == timedelta(seconds=30)
        assert parse_interval("5s") == timedelta(seconds=5)
    
    def test_parse_minutes(self):
        assert parse_interval("30m") == timedelta(minutes=30)
        assert parse_interval("15m") == timedelta(minutes=15)
    
    def test_parse_hours(self):
        assert parse_interval("1h") == timedelta(hours=1)
        assert parse_interval("2h") == timedelta(hours=2)
    
    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_interval("invalid")
        
        with pytest.raises(ValueError):
            parse_interval("30x")


class TestIsDeliverable:
    """Tests for is_deliverable filter function"""
    
    def test_deliverable_response(self):
        assert is_deliverable("Here is your report: Task completed successfully") is True
    
    def test_finalization_fallback_filtered(self):
        assert is_deliverable("I couldn't produce a final answer due to empty response") is False
    
    def test_leaked_reasoning_filtered(self):
        assert is_deliverable("Judgment call: I need to check heartbeat.md for tasks") is False
        assert is_deliverable("My instructions say I must follow strict heartbeat interpretation") is False
        assert is_deliverable("i am supposed to read HEARTBEAT.md and respond") is False
    
    def test_empty_response_handled(self):
        assert is_deliverable("") is True  # Empty is valid "nothing to report"
    
    def test_mixed_content(self):
        assert is_deliverable("Task completed. Note: I checked heartbeat.md as instructed.") is False


class TestHeartbeatFileParsing:
    """Tests for heartbeat file parsing"""
    
    def test_parse_checklist_mode(self):
        content = """# Heartbeat Tasks

## Active Tasks
- [ ] Review code for bugs
- [ ] Update documentation
- [ ] Run tests
"""
        result = parse_heartbeat_file(content)
        assert result["mode"] == "checklist"
        assert len(result["tasks"]) == 3
        assert result["tasks"][0]["name"] == "Review code for bugs"
    
    def test_parse_yaml_mode(self):
        content = """# Heartbeat Tasks

tasks:
- name: Review code
  interval: 30m
  prompt: Review the codebase for issues
"""
        result = parse_heartbeat_file(content)
        assert result["mode"] == "tasks_block"
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["name"] == "Review code"
        assert result["tasks"][0]["interval"] == "30m"
    
    def test_parse_empty_file(self):
        content = "# Heartbeat Tasks\n\nNothing yet."
        result = parse_heartbeat_file(content)
        assert result["tasks"] == []


class TestHeartbeatScheduler:
    """Tests for HeartbeatScheduler class"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        agent_executor = AsyncMock(return_value="HEARTBEAT_OK")
        config = {
            "enabled": True,
            "every": "15m",
            "skip_when_busy": True,
        }
        
        scheduler = HeartbeatScheduler(agent_executor=agent_executor, config=config)
        
        assert scheduler.enabled is True
        assert scheduler.interval == timedelta(minutes=15)
        assert scheduler.skip_when_busy is True
    
    @pytest.mark.asyncio
    async def test_decision_skip(self):
        async def mock_executor(prompt):
            return "No tasks to report, HEARTBEAT_OK"
        
        scheduler = HeartbeatScheduler(
            agent_executor=mock_executor,
            config={"enabled": True}
        )
        
        action, tasks = await scheduler._decide("Just a reminder note, nothing urgent")
        assert action == "skip"
    
    @pytest.mark.asyncio
    async def test_skip_with_no_heartbeat_file(self):
        async def mock_executor(prompt):
            return "ok"
        
        scheduler = HeartbeatScheduler(
            agent_executor=mock_executor,
            config={"enabled": True}
        )
        
        with patch("core.agents.heartbeat_scheduler.get_heartbeat_file", return_value=None):
            result = await scheduler._run_heartbeat()
            assert "skipped" in result
    
    @pytest.mark.asyncio
    async def test_active_hours_check(self):
        # Mock outside active hours
        with patch("core.agents.heartbeat_scheduler.is_within_active_hours", return_value=False):
            async def mock_executor(prompt):
                return "ok"
            
            scheduler = HeartbeatScheduler(
                agent_executor=mock_executor,
                config={"enabled": True, "every": "5m"}
            )
            
            result = await scheduler._run_heartbeat()
            assert "outside active hours" in result
    
    @pytest.mark.asyncio
    async def test_busy_skip(self):
        async def mock_executor(prompt):
            return "ok"
        
        scheduler = HeartbeatScheduler(
            agent_executor=mock_executor,
            config={"enabled": True, "skip_when_busy": True}
        )
        scheduler.set_busy(True)
        
        with patch("core.agents.heartbeat_scheduler.get_heartbeat_file", return_value=Path("/tmp/test.md")):
            with patch("core.agents.heartbeat_scheduler.is_within_active_hours", return_value=True):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "tasks"
                    result = await scheduler._run_heartbeat()
                    assert "agent busy" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])