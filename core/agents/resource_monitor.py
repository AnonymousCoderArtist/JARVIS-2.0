"""Resource Monitor for tracking CPU, memory, and I/O usage"""

import asyncio
import logging
import os
import psutil
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Snapshot of system resource usage"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float


@dataclass
class ResourceLimits:
    """Resource limits for monitoring"""
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 80.0
    max_memory_mb: float = 512.0
    alert_threshold: float = 90.0  # Alert when usage exceeds this


class ResourceMonitor:
    """Monitors system resources and provides alerts"""

    def __init__(
        self,
        limits: ResourceLimits | None = None,
        update_interval: float = 1.0,
        alert_callback: Callable[[ResourceSnapshot], None] | None = None
    ):
        self.limits = limits or ResourceLimits()
        self.update_interval = update_interval
        self.alert_callback = alert_callback
        
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None
        self._snapshots: list[ResourceSnapshot] = []
        self._max_snapshots = 100  # Keep last 100 snapshots
        
        # Track I/O counters for delta calculation
        self._last_disk_io = psutil.disk_io_counters()
        self._last_network_io = psutil.net_io_counters()
        self._last_io_time = time.time()

    async def start_monitoring(self) -> None:
        """Start resource monitoring"""
        if self._monitoring:
            logger.warning("Resource monitoring already started")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started resource monitoring")

    async def stop_monitoring(self) -> None:
        """Stop resource monitoring"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped resource monitoring")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                snapshot = await self._take_snapshot()
                self._add_snapshot(snapshot)
                
                # Check for resource alerts
                if self._should_alert(snapshot):
                    if self.alert_callback:
                        self.alert_callback(snapshot)
                    logger.warning(f"Resource alert: CPU={snapshot.cpu_percent}%, Memory={snapshot.memory_percent}%")
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def _take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resource usage"""
        current_time = time.time()
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk I/O (calculate delta)
        disk_io = psutil.disk_io_counters()
        disk_io_read_mb = 0.0
        disk_io_write_mb = 0.0
        
        if self._last_disk_io and disk_io:
            time_delta = current_time - self._last_io_time
            if time_delta > 0:
                read_bytes = disk_io.read_bytes - self._last_disk_io.read_bytes
                write_bytes = disk_io.write_bytes - self._last_disk_io.write_bytes
                disk_io_read_mb = (read_bytes / (1024 * 1024)) / time_delta
                disk_io_write_mb = (write_bytes / (1024 * 1024)) / time_delta
        
        self._last_disk_io = disk_io
        
        # Network I/O (calculate delta)
        network_io = psutil.net_io_counters()
        network_io_sent_mb = 0.0
        network_io_recv_mb = 0.0
        
        if self._last_network_io and network_io:
            time_delta = current_time - self._last_io_time
            if time_delta > 0:
                sent_bytes = network_io.bytes_sent - self._last_network_io.bytes_sent
                recv_bytes = network_io.bytes_recv - self._last_network_io.bytes_recv
                network_io_sent_mb = (sent_bytes / (1024 * 1024)) / time_delta
                network_io_recv_mb = (recv_bytes / (1024 * 1024)) / time_delta
        
        self._last_network_io = network_io
        self._last_io_time = current_time
        
        return ResourceSnapshot(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            network_io_sent_mb=network_io_sent_mb,
            network_io_recv_mb=network_io_recv_mb
        )

    def _add_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """Add a snapshot to history"""
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

    def _should_alert(self, snapshot: ResourceSnapshot) -> bool:
        """Check if resource usage should trigger an alert"""
        return (
            snapshot.cpu_percent > self.limits.alert_threshold or
            snapshot.memory_percent > self.limits.alert_threshold
        )

    def get_current_snapshot(self) -> ResourceSnapshot | None:
        """Get the most recent snapshot"""
        if self._snapshots:
            return self._snapshots[-1]
        return None

    def get_average_usage(self, duration_seconds: float = 60.0) -> dict[str, float]:
        """
        Get average resource usage over a time period
        
        Args:
            duration_seconds: Time period to average over
            
        Returns:
            Dictionary with average usage metrics
        """
        current_time = time.time()
        recent_snapshots = [
            s for s in self._snapshots
            if current_time - s.timestamp <= duration_seconds
        ]
        
        if not recent_snapshots:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "memory_used_mb": 0.0,
                "disk_io_read_mb": 0.0,
                "disk_io_write_mb": 0.0,
            }
        
        return {
            "cpu_percent": sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots),
            "memory_percent": sum(s.memory_percent for s in recent_snapshots) / len(recent_snapshots),
            "memory_used_mb": sum(s.memory_used_mb for s in recent_snapshots) / len(recent_snapshots),
            "disk_io_read_mb": sum(s.disk_io_read_mb for s in recent_snapshots) / len(recent_snapshots),
            "disk_io_write_mb": sum(s.disk_io_write_mb for s in recent_snapshots) / len(recent_snapshots),
        }

    def check_limits(self, snapshot: ResourceSnapshot | None = None) -> dict[str, bool]:
        """
        Check if current resource usage exceeds limits
        
        Args:
            snapshot: Snapshot to check (uses current if None)
            
        Returns:
            Dictionary with limit check results
        """
        if snapshot is None:
            snapshot = self.get_current_snapshot()
        
        if snapshot is None:
            return {
                "cpu_exceeded": False,
                "memory_percent_exceeded": False,
                "memory_mb_exceeded": False,
            }
        
        return {
            "cpu_exceeded": snapshot.cpu_percent > self.limits.max_cpu_percent,
            "memory_percent_exceeded": snapshot.memory_percent > self.limits.max_memory_percent,
            "memory_mb_exceeded": snapshot.memory_used_mb > self.limits.max_memory_mb,
        }

    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        return self._monitoring

    def get_snapshot_count(self) -> int:
        """Get the number of stored snapshots"""
        return len(self._snapshots)
