import logging
import os
import subprocess
import time
from pathlib import Path

# Cross-platform subprocess creation flags
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

logger = logging.getLogger(__name__)

class ProjectIndexer:
    """Fast project file indexer using ripgrep"""

    def __init__(self, root_dir: str | Path | None = None):
        self.root_dir = Path(root_dir or os.getcwd()).resolve()
        self._files: list[str] = []
        self._last_index_time = 0
        self._cache_duration = 10  # Index expires every 10 seconds for freshness

    def get_files(self) -> list[str]:
        """Get list of project files, with caching"""
        current_time = time.time()
        if not self._files or (current_time - self._last_index_time > self._cache_duration):
            self._index_files()
        return self._files

    def _index_files(self):
        """Index files using ripgrep or fallback to os.walk"""
        try:
            # Use rg --files which is extremely fast and respects .gitignore
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = CREATE_NO_WINDOW
            result = subprocess.run(
                ["rg", "--files", "--hidden", "--glob", "!.git/*"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True,
                **kwargs
            )
            self._files = result.stdout.splitlines()
            self._last_index_time = time.time()
            logger.debug(f"Indexed {len(self._files)} files using ripgrep")
        except Exception as e:
            logger.warning(f"Ripgrep indexing failed, falling back to os.walk: {e}")
            self._files = []
            try:
                for root, dirs, files in os.walk(self.root_dir):
                    # Skip common heavy/ignored directories
                    for skip in ['.git', '.venv', 'node_modules', '__pycache__', '.gemini', '.jarvis']:
                        if skip in dirs:
                            dirs.remove(skip)

                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.root_dir)
                        self._files.append(rel_path.replace("\\", "/"))
                self._last_index_time = time.time()
            except Exception as walk_err:
                logger.error(f"Fallback indexing failed: {walk_err}")

    def search(self, query: str, limit: int = 20) -> list[tuple[str, str, str]]:
        """Search files using simple fuzzy matching and ranking"""
        files = self.get_files()

        if query.startswith("@"):
            query_name = query[1:].lower()
            results = []
            for f in files:
                name = os.path.basename(f).lower()
                if name.startswith(query_name):
                    results.append(f)
            results = sorted(results, key=lambda x: (len(x), x))

            final_results = []
            for f in results:
                name = os.path.basename(f)
                path = os.path.dirname(f)
                is_dir = os.path.isdir(os.path.join(self.root_dir, f))
                label = name + ("/" if is_dir else "")
                final_results.append((label, path, f))
            return final_results

        query = query.lower()
        results = []

        for f in files:
            f_lower = f.lower()
            name = os.path.basename(f)
            name_lower = name.lower()

            score = 0
            if query == name_lower:
                score = 100
            elif name_lower.startswith(query):
                score = 80
            elif query in name_lower:
                score = 60
            elif query in f_lower:
                score = 40

            if score > 0:
                results.append((score, f))

        results.sort(key=lambda x: (-x[0], len(x[1])))

        final_results = []
        for _, f in results[:limit]:
            name = os.path.basename(f)
            path = os.path.dirname(f)
            is_dir = os.path.isdir(os.path.join(self.root_dir, f))
            # Label without icon, description is path, replacement is full relative path
            label = name + ("/" if is_dir else "")
            final_results.append((label, path, f))

        return final_results
