"""Dynamic loading of JARVIS extension modules.

Extensions are Python files that export an async factory function.
Loading uses standard ``importlib`` — no JIT compiler needed.

Discovery paths (in precedence order):
1. ``.jarvis/extensions/*.py`` (project-local, highest priority)
2. ``~/.jarvis/extensions/*.py`` (global user extensions)
3. pip-installed packages registered via entry point ``jarvis.extensions``
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from core.extensions.types import ExtensionLoadResult, ExtensionManifest

logger = logging.getLogger(__name__)

# The entry point group name for pip-distributed extensions
ENTRY_POINT_GROUP = "jarvis.extensions"

# Default discovery paths
PROJECT_EXTENSIONS_DIR = Path(".jarvis") / "extensions"
USER_EXTENSIONS_DIR = Path.home() / ".jarvis" / "extensions"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_extension_paths(
    project_dir: str | Path | None = None,
) -> list[Path]:
    """Return a list of ``.py`` file paths from all discovery directories.

    Results are ordered by precedence (project-first, then user, then pip).
    Duplicate filenames (same stem) de-duplicate in favour of higher
    precedence.
    """
    seen: set[str] = set()
    paths: list[Path] = []

    # 1. Project-local
    if project_dir is not None:
        proj = Path(project_dir) / PROJECT_EXTENSIONS_DIR
        for p in sorted(proj.glob("*.py")):
            if p.stem not in seen:
                seen.add(p.stem)
                paths.append(p)

    # 2. User global
    for p in sorted(USER_EXTENSIONS_DIR.glob("*.py")):
        if p.stem not in seen:
            seen.add(p.stem)
            paths.append(p)

    # 3. pip entry points
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            if ep.name not in seen:
                seen.add(ep.name)
                # entry points don't map to files we can return here;
                # they are loaded directly in load_from_entry_point()
    except Exception:
        pass

    return paths


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_from_file(file_path: str | Path) -> ExtensionLoadResult:
    """Load a single extension from a ``.py`` file.

    The file must export either:
    - A top-level ``async def jarvis_extension(api): ...`` function, **or**
    - A top-level ``async def __jarvis_extension__(api): ...`` function, **or**
    - A ``default`` export that is a coroutine function receiving ``api``.
    """
    path = Path(file_path)
    if not path.exists():
        return ExtensionLoadResult(
            success=False,
            error=f"Extension file not found: {path}",
        )

    module_name = f"_jarvis_ext_{path.stem}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return ExtensionLoadResult(
                success=False,
                error=f"Failed to create module spec for {path}",
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Look for the factory function — try preferred names
        factory = None
        for attr_name in ("jarvis", "jarvis_extension", "__jarvis_extension__", "default"):
            fn = getattr(module, attr_name, None)
            if fn is not None and callable(fn):
                factory = fn
                break

        if factory is None:
            return ExtensionLoadResult(
                success=False,
                error=f"No factory function found in {path}. "
                      f"Export 'async def jarvis_extension(api): ...'",
            )

        # Build manifest from module-level attributes if present
        manifest = ExtensionManifest(
            name=path.stem,
            version=getattr(module, "__version__", "1.0.0"),
            description=getattr(module, "__description__", ""),
            author=getattr(module, "__author__", ""),
            source_path=str(path.resolve()),
        )

        return ExtensionLoadResult(
            success=True,
            manifest=manifest,
            factory_fn=factory,
        )

    except Exception as exc:
        logger.exception("Failed to load extension from %s", path)
        return ExtensionLoadResult(
            success=False,
            error=str(exc),
        )


def load_from_directory(dir_path: str | Path) -> list[ExtensionLoadResult]:
    """Load all ``.py`` files from *dir_path*."""
    results: list[ExtensionLoadResult] = []
    for py_file in sorted(Path(dir_path).glob("*.py")):
        result = load_from_file(py_file)
        results.append(result)
    return results


def load_from_entry_point(name: str) -> ExtensionLoadResult:
    """Load an extension registered via pip entry point."""
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            if ep.name == name:
                factory = ep.load()
                manifest = ExtensionManifest(
                    name=name,
                    version=getattr(factory, "__version__", "1.0.0"),
                    description=getattr(factory, "__description__", ""),
                    author=getattr(factory, "__author__", ""),
                    source_path=f"entrypoint:{ENTRY_POINT_GROUP}/{name}",
                )
                return ExtensionLoadResult(
                    success=True,
                    manifest=manifest,
                    factory_fn=factory,
                )
        return ExtensionLoadResult(
            success=False,
            error=f"Entry point '{name}' not found in group '{ENTRY_POINT_GROUP}'",
        )
    except Exception as exc:
        return ExtensionLoadResult(
            success=False,
            error=str(exc),
        )


def discover_and_load_all(
    project_dir: str | Path | None = None,
    extra_paths: list[str | Path] | None = None,
) -> list[ExtensionLoadResult]:
    """Convenience: discover all extension paths and load every one.

    Returns a flat list of ``ExtensionLoadResult`` (successful and failed).
    """
    paths = discover_extension_paths(project_dir)

    if extra_paths:
        for p in extra_paths:
            pp = Path(p)
            if pp.exists() and pp.suffix == ".py":
                paths.append(pp)
            elif pp.exists() and pp.is_dir():
                paths.extend(sorted(pp.glob("*.py")))

    results: list[ExtensionLoadResult] = []
    for path in paths:
        result = load_from_file(path)
        results.append(result)

    return results
