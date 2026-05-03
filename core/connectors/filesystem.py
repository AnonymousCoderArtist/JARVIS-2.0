"""Filesystem connector for JARVIS"""

import os
from pathlib import Path
from typing import Any

from .base import BaseConnector, ConnectorConfig


class FilesystemConnector(BaseConnector):
    """Connector for local filesystem access"""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.root_dir = Path(config.config.get("root_dir", "."))
        self.include_hidden = config.config.get("include_hidden", False)
        self.max_depth = config.config.get("max_depth", 10)

    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for files matching query."""
        results = []
        search_terms = query.lower().split()

        for file_path in self._iter_files():
            if len(results) >= limit:
                break

            # Check if file matches search terms
            file_name = file_path.name.lower()
            if any(term in file_name or term in str(file_path).lower() for term in search_terms):
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
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
                return "\n".join(lines)
        except Exception:
            return f"[Binary file: {file_path.name}]"