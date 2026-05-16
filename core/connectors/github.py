"""GitHub connector - fetches notifications, issues, and PRs from GitHub"""

import json
import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)

from .base import BaseConnector, ConnectorConfig, Document, SyncStatus
from .registry import ConnectorRegistry

DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_CONFIG_DIR = Path.home() / ".jarvis" / "credentials"


def _github_api_get(
    token: str,
    endpoint: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None
) -> Any:
    """Call GitHub API"""
    if not HAS_HTTPX:
        raise ImportError("httpx is required for github connector: pip install httpx")

    default_headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "JARVIS-Assistant"
    }
    if token:
        default_headers["Authorization"] = f"token {token}"

    if headers:
        default_headers.update(headers)

    resp = httpx.get(
        f"{DEFAULT_API_BASE}{endpoint}",
        headers=default_headers,
        params=params or {},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


@ConnectorRegistry.register("github")
class GitHubConnector(BaseConnector):
    """Fetch GitHub notifications, issues, and PRs"""

    connector_id = "github"
    display_name = "GitHub"
    auth_type = "token"

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config)
        self._token = ""
        self._username = ""
        self._repos = []  # List of repos to monitor
        self._status = SyncStatus()
        self._load_credentials()

    def _load_credentials(self):
        """Load token from credentials"""
        creds = self._load_credentials()
        self._token = creds.get("token", "")

        if not self._token:
            self._token = self.config.get_credential("token", "")

        self._username = creds.get("username", "")
        self._repos = creds.get("repos", [])

    def is_connected(self) -> bool:
        return bool(self._token)

    def disconnect(self) -> None:
        self._token = ""
        self._username = ""

    def sync(
        self, *, since: datetime | None = None, cursor: str | None = None
    ) -> Iterator[Document]:
        """Fetch notifications and repo data"""
        if not self.is_connected():
            return

        since = since or (datetime.now() - timedelta(days=7))

        # 1. Fetch notifications
        try:
            notifications = _github_api_get(
                self._token,
                "/notifications",
                {"since": since.isoformat(), "all": "false"}
            )

            for notif in notifications[:15]:  # Limit to 15
                repo = notif.get("repository", {})
                subject = notif.get("subject", {})

                yield Document(
                    doc_id=f"github-notif-{notif.get('id', '')}",
                    source="github",
                    doc_type="notification",
                    content=json.dumps(notif),
                    title=subject.get("title", "No title"),
                    author=notif.get("repository", {}).get("full_name", ""),
                    timestamp=datetime.fromisoformat(
                        notif.get("updated_at", "").replace("Z", "+00:00")
                    ),
                    url=subject.get("url", ""),
                    metadata={
                        "reason": notif.get("reason"),
                        "unread": notif.get("unread"),
                        "repo": repo.get("full_name"),
                        "type": subject.get("type"),
                    }
                )
        except Exception as e:
            self._status.error = str(e)

        # 2. Fetch issues for configured repos
        for repo in self._repos[:5]:  # Limit to 5 repos
            try:
                issues = _github_api_get(
                    self._token,
                    f"/repos/{repo}/issues",
                    {"state": "open", "sort": "updated", "per_page": "10"}
                )

                for issue in issues:
                    # Skip PRs (they're also returned as issues)
                    if "pull_request" in issue:
                        continue

                    created = datetime.fromisoformat(
                        issue.get("created_at", "").replace("Z", "+00:00")
                    )
                    if created < since:
                        continue

                    yield Document(
                        doc_id=f"github-issue-{issue.get('id', '')}",
                        source="github",
                        doc_type="issue",
                        content=issue.get("body", ""),
                        title=issue.get("title", "No title"),
                        author=issue.get("user", {}).get("login", ""),
                        timestamp=created,
                        url=issue.get("html_url", ""),
                        metadata={
                            "repo": repo,
                            "state": issue.get("state"),
                            "comments": issue.get("comments"),
                            "labels": [l.get("name") for l in issue.get("labels", [])],
                        }
                    )
            except Exception as e:
                logger.debug(f"Failed to fetch issues for {repo}: {e}")

        # 3. Fetch PRs for configured repos
        for repo in self._repos[:5]:
            try:
                prs = _github_api_get(
                    self._token,
                    f"/repos/{repo}/pulls",
                    {"state": "open", "sort": "updated", "per_page": "10"}
                )

                for pr in prs:
                    created = datetime.fromisoformat(
                        pr.get("created_at", "").replace("Z", "+00:00")
                    )
                    if created < since:
                        continue

                    yield Document(
                        doc_id=f"github-pr-{pr.get('id', '')}",
                        source="github",
                        doc_type="pull_request",
                        content=pr.get("body", ""),
                        title=pr.get("title", "No title"),
                        author=pr.get("user", {}).get("login", ""),
                        timestamp=created,
                        url=pr.get("html_url", ""),
                        metadata={
                            "repo": repo,
                            "state": pr.get("state"),
                            "draft": pr.get("draft", False),
                            "merged": pr.get("merged", False),
                        }
                    )
            except Exception as e:
                logger.debug(f"Failed to fetch PRs for {repo}: {e}")

        self._status.state = "idle"
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    # --- Legacy methods ---

    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        docs = list(self.sync())
        return [doc.to_dict() for doc in docs[:limit]]

    def supports_query_type(self, query_type: str) -> bool:
        return query_type in ["github", "issues", "notifications"]

    def get_capabilities(self) -> list[str]:
        return ["notifications", "issues", "pull_requests"]

    # --- Configuration ---

    def set_credentials(self, token: str, username: str, repos: list[str] | None = None) -> None:  #type : ignore
        """Set GitHub token, username, and repos to monitor"""
        self._token = token
        self._username = username
        self._repos = repos or []
        self._save_credentials({
            "token": token,
            "username": username,
            "repos": self._repos,
        })

    def add_repo(self, repo: str) -> None:
        """Add a repo to monitor"""
        if repo not in self._repos:
            self._repos.append(repo)
            self._save_credentials({
                "token": self._token,
                "username": self._username,
                "repos": self._repos,
            })


# For backward compatibility
GitHubConnectorV2 = GitHubConnector
