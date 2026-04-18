"""Safety manager for permission system and checkpoint management"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Checkpoint:
    """A system checkpoint for undo functionality"""
    id: str
    timestamp: datetime = field(default_factory=datetime.now)
    state: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class SafetyManager:
    """Manages safety checks and permissions"""

    def __init__(self, require_confirmation: bool = True, auto_checkpoint: bool = True, max_checkpoints: int = 10):
        self.require_confirmation = require_confirmation
        self.auto_checkpoint = auto_checkpoint
        self.max_checkpoints = max_checkpoints
        self.checkpoints: list[Checkpoint] = []
        self.destructive_keywords = [
            "delete", "remove", "erase", "format", "wipe",
            "overwrite", "replace", "truncate", "drop"
        ]

    async def check_action(self, action: dict) -> bool:
        """
        Check if an action requires confirmation

        Args:
            action: Dictionary describing the action

        Returns:
            True if action is allowed, False if denied
        """
        if self._is_destructive(action):
            if self.require_confirmation:
                return await self._request_confirmation(action)
            return True
        return True

    def _is_destructive(self, action: dict) -> bool:
        """
        Detect if an action is destructive

        Args:
            action: Dictionary describing the action

        Returns:
            True if destructive, False otherwise
        """
        action_str = str(action).lower()

        # Check for destructive keywords
        for keyword in self.destructive_keywords:
            if keyword in action_str:
                return True

        # Check for destructive tool names
        tool_name = action.get("tool", "")
        if tool_name in ["delete_file", "remove_directory", "format_disk"]:
            return True

        return False

    async def _request_confirmation(self, action: dict) -> bool:
        """
        Request user confirmation for a destructive action

        Args:
            action: Dictionary describing the action

        Returns:
            True if confirmed, False otherwise
        """
        action_desc = self._describe_action(action)
        print(f"\n⚠️  Destructive action detected: {action_desc}")
        response = input("Do you want to proceed? (yes/no): ").strip().lower()

        return response in ["yes", "y"]

    def _describe_action(self, action: dict) -> str:
        """
        Generate a human-readable description of an action

        Args:
            action: Dictionary describing the action

        Returns:
            Description string
        """
        tool = action.get("tool", "unknown")
        params = action.get("parameters", {})
        return f"{tool} with parameters {params}"

    def create_checkpoint(self, state: dict, metadata: dict | None = None) -> str:
        """
        Create a checkpoint for undo functionality

        Args:
            state: Current system state
            metadata: Optional metadata

        Returns:
            Checkpoint ID
        """
        if not self.auto_checkpoint:
            return ""

        checkpoint_id = f"ckpt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        checkpoint = Checkpoint(
            id=checkpoint_id,
            state=state.copy(),
            metadata=metadata or {}
        )

        self.checkpoints.append(checkpoint)

        # Maintain max checkpoint limit
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.pop(0)

        return checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str) -> dict | None:
        """
        Restore system state from a checkpoint

        Args:
            checkpoint_id: Checkpoint ID to restore

        Returns:
            Restored state or None if not found
        """
        for checkpoint in self.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint.state.copy()
        return None

    def list_checkpoints(self) -> list[dict]:
        """
        List all available checkpoints

        Returns:
            List of checkpoint information
        """
        return [
            {
                "id": cp.id,
                "timestamp": cp.timestamp.isoformat(),
                "metadata": cp.metadata
            }
            for cp in self.checkpoints
        ]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            True if successful, False otherwise
        """
        for i, checkpoint in enumerate(self.checkpoints):
            if checkpoint.id == checkpoint_id:
                self.checkpoints.pop(i)
                return True
        return False

    def clear_checkpoints(self):
        """Clear all checkpoints"""
        self.checkpoints.clear()

    def save_checkpoints_to_disk(self, filepath: str):
        """
        Save checkpoints to disk

        Args:
            filepath: Path to save checkpoints
        """
        checkpoint_data = [
            {
                "id": cp.id,
                "timestamp": cp.timestamp.isoformat(),
                "state": cp.state,
                "metadata": cp.metadata
            }
            for cp in self.checkpoints
        ]

        with open(filepath, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

    def load_checkpoints_from_disk(self, filepath: str):
        """
        Load checkpoints from disk

        Args:
            filepath: Path to load checkpoints from
        """
        if not os.path.exists(filepath):
            return

        with open(filepath) as f:
            checkpoint_data = json.load(f)

        self.checkpoints = [
            Checkpoint(
                id=cp["id"],
                timestamp=datetime.fromisoformat(cp["timestamp"]),
                state=cp["state"],
                metadata=cp.get("metadata", {})
            )
            for cp in checkpoint_data
        ]

    def get_stats(self) -> dict:
        """Get safety manager statistics"""
        return {
            "require_confirmation": self.require_confirmation,
            "auto_checkpoint": self.auto_checkpoint,
            "max_checkpoints": self.max_checkpoints,
            "current_checkpoints": len(self.checkpoints)
        }
