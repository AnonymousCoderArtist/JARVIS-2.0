"""Filesystem connector for JARVIS - Updated for new connector system"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, List, Optional

from .base import BaseConnector, ConnectorConfig, Document, SyncStatus
from .registry import ConnectorRegistry


@ConnectorRegistry.register("filesystem")
class FilesystemConnector(BaseConnector):
    """Connector for local filesystem access - Updated with new interface"""
    
    connector_id = "filesystem"
    display_name = "Local Filesystem"
    auth_type = "none"  # No auth needed for local filesystem
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        if config is None:
            config = ConnectorConfig(name="filesystem", connector_type="filesystem")
        super().__init__(config)
        self.root_dir = Path(self.config.config.get("root_dir", "."))
        self.include_hidden = self.config.config.get("include_hidden", False)
        self.max_depth = self.config.config.get("max_depth", 10)
        self._status = SyncStatus()
    
    # --- New interface methods (for sync) ---
    
    def is_connected(self) -> bool:
        """Always connected for local filesystem"""
        return True
    
    def disconnect(self) -> None:
        """Nothing to disconnect for local filesystem"""
        pass
    
    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        """Yield recent files as Documents"""
        
        search_terms = []  # Could be extended to accept a query
        max_files = 15
        
        count = 0
        for file_path in self._iter_files():
            if count >= max_files:
                break
            
            try:
                if not file_path.exists():
                    continue
                
                stat = file_path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                
                # Filter by since if provided
                if since and mtime < since:
                    continue
                
                # Create Document
                yield Document(
                    doc_id=str(file_path),
                    source="filesystem",
                    doc_type="file",
                    content=self._read_file_preview(file_path)[:500],
                    title=file_path.name,
                    timestamp=mtime,
                    metadata={
                        "path": str(file_path),
                        "size": stat.st_size,
                        "is_dir": file_path.is_dir(),
                    }
                )
                count += 1
                
            except Exception as e:
                continue
        
        self._status.state = "idle"
        self._status.last_sync = datetime.now()
        self._status.items_synced = count
    
    def sync_status(self) -> SyncStatus:
        return self._status
    
    # --- Legacy methods (for backward compatibility) ---
    
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for files matching query."""
        results = []
        search_terms = query.lower().split() if query else []

        for file_path in self._iter_files():
            if len(results) >= limit:
                break

            # Check if file matches search terms
            file_name = file_path.name.lower()
            if not search_terms or any(term in file_name or term in str(file_path).lower() for term in search_terms):
                try:
                    content = self._read_file_preview(file_path)
                    results.append(self.format_item({
                        "id": str(file_path),
                        "path": str(file_path),
                        "name": file_path.name,
                        "content": content,
                        "metadata": {
                            "size": file_path.stat().st_size if file_path.exists() else 0,
                            "modified": file_path.stat().st_mtime if file_path.exists() else None,
                            "is_dir": file_path.is_dir(),
                        }
                    }))
                except Exception:
                    continue

        return results

    def supports_query_type(self, query_type: str) -> bool:
        return query_type in ("files", "filesystem", "code", "documents")
    
    def get_capabilities(self) -> list[str]:
        return ["file_read", "directory_list", "glob_search", "file_metadata"]
    
    # --- Helper methods ---
    
    def _iter_files(self):
        """Iterate through files in root directory."""
        if not self.root_dir.exists():
            return

        root_str = str(self.root_dir)
        root_sep_count = root_str.count(os.sep)

        for root, dirs, files in os.walk(self.root_dir):
            # Filter hidden directories
            if not self.include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]

            # Check depth limit
            depth = str(root).count(os.sep) - root_sep_count
            if depth >= self.max_depth:
                dirs.clear()
                continue

            for file in files:
                if not self.include_hidden and file.startswith("."):
                    continue
                yield Path(root) / file

    def _read_file_preview(self, file_path: Path, max_lines: int = 50) -> str:
        """Read a preview of file content."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
                return "\n".join(lines)
        except Exception:
            return f"[Binary file: {file_path.name}]"


# For backward compatibility
FilesystemConnectorV2 = FilesystemConnector