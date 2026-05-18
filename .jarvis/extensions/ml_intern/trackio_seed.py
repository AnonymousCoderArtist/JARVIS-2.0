"""Seed an HF Space with the trackio dashboard."""

from __future__ import annotations

import io
from typing import Callable, Optional

from huggingface_hub import (
    HfApi,
    Volume,
    add_space_variable,
    create_bucket,
    create_repo,
)
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError


_README = """---
title: Trackio Dashboard
emoji: 📊
colorFrom: pink
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
tags:
  - trackio
---

Embedded trackio dashboard for ml-intern runs.
"""

_REQUIREMENTS = "trackio\n"
_APP_PY = "import trackio\ntrackio.show()\n"

_LOGO_URL = (
    "https://huggingface.co/spaces/smolagents/ml-intern/"
    "resolve/main/frontend/public/smolagents.webp"
)

_FILES = {
    "README.md": _README,
    "requirements.txt": _REQUIREMENTS,
    "app.py": _APP_PY,
}


def _already_seeded(api: HfApi, space_id: str) -> bool:
    try:
        path = api.hf_hub_download(
            repo_id=space_id, repo_type="space", filename="app.py"
        )
    except (EntryNotFoundError, RepositoryNotFoundError, OSError):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            return "trackio.show" in f.read()
    except OSError:
        return False


def _get_space_volumes(api: HfApi, space_id: str) -> list:
    runtime = api.get_space_runtime(space_id)
    if getattr(runtime, "volumes", None):
        return list(runtime.volumes)  # ty:ignore[invalid-argument-type]
    info = api.space_info(space_id)
    if info.runtime and getattr(info.runtime, "volumes", None):
        return list(info.runtime.volumes) # ty:ignore[invalid-argument-type]
    return []


def _ensure_bucket_mounted(
    api: HfApi,
    space_id: str,
    bucket_id: str,
    hf_token: str,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    create_bucket(bucket_id, private=True, exist_ok=True, token=hf_token)

    existing = _get_space_volumes(api, space_id)
    already_mounted = any(
        getattr(v, "type", None) == "bucket"
        and getattr(v, "source", None) == bucket_id
        and getattr(v, "mount_path", None) == "/data"
        for v in existing
    )
    if not already_mounted:
        preserved = [
            v
            for v in existing
            if not (
                getattr(v, "type", None) == "bucket"
                and (
                    getattr(v, "source", None) == bucket_id
                    or getattr(v, "mount_path", None) == "/data"
                )
            )
        ]
        api.set_space_volumes(
            space_id,
            preserved + [Volume(type="bucket", source=bucket_id, mount_path="/data")],
        )
        if log:
            log(f"mounted bucket {bucket_id} at /data on {space_id}")

    variables = api.get_space_variables(space_id)
    desired = {
        "TRACKIO_DIR": "/data/trackio",
        "TRACKIO_BUCKET_ID": bucket_id,
        "TRACKIO_LOGO_LIGHT_URL": _LOGO_URL,
        "TRACKIO_LOGO_DARK_URL": _LOGO_URL,
    }
    for key, value in desired.items():
        if getattr(variables.get(key), "value", None) != value:
            add_space_variable(space_id, key, value, token=hf_token)


def ensure_trackio_dashboard(
    space_id: str,
    hf_token: str,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    api = HfApi(token=hf_token)

    create_repo(
        repo_id=space_id,
        repo_type="space",
        space_sdk="gradio",
        exist_ok=True,
        token=hf_token,
    )

    seeded_files = False
    if _already_seeded(api, space_id):
        if log:
            log(f"trackio dashboard already seeded on {space_id}")
    else:
        if log:
            log(f"seeding trackio dashboard files into {space_id}")
        for path_in_repo, content in _FILES.items():
            api.upload_file(
                path_or_fileobj=io.BytesIO(content.encode("utf-8")),
                path_in_repo=path_in_repo,
                repo_id=space_id,
                repo_type="space",
                commit_message=f"ml-intern: seed trackio dashboard ({path_in_repo})",
            )
        seeded_files = True

    bucket_id = f"{space_id}-bucket"
    _ensure_bucket_mounted(api, space_id, bucket_id, hf_token, log)

    if log:
        log(f"trackio dashboard ready: https://huggingface.co/spaces/{space_id}")
    return seeded_files
