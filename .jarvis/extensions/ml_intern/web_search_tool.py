"""Web search tool — DuckDuckGo HTML search with domain filtering.

Ported from huggingface/ml-intern agent/tools/web_search_tool.py.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

import requests as _requests

from jarvis.api import BaseTool, ToolInput, ToolOutput

DEFAULT_SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "jarvis-ml-intern/0.1"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RESULTS = 8


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str

    def as_json(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url}


class _AnchorParser(HTMLParser):
    def __init__(self, *, require_result_class: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.require_result_class = require_result_class
        self.hits: list[tuple[str, str]] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        href = attr_map.get("href")
        if not href:
            return
        if self.require_result_class and "result__a" not in attr_map.get("class", ""):
            return
        self._active_href = href
        self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._active_href is not None:
            self._active_text.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._active_href is not None:
            self._active_text.append(f"&#{name};")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._active_href is None:
            return
        title = " ".join("".join(self._active_text).split())
        title = html.unescape(title).strip()
        self.hits.append((self._active_href, title))
        self._active_href = None
        self._active_text = []


def _build_search_url(query: str) -> str:
    base = os.environ.get("ML_INTERN_WEB_SEARCH_BASE_URL", DEFAULT_SEARCH_URL)
    parsed = urlparse(base)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query_pairs.append(("q", query))
    return urlunparse(parsed._replace(query=urlencode(query_pairs)))


def _decode_ddg_redirect(url: str) -> str | None:
    if url.startswith("http://") or url.startswith("https://"):
        return html.unescape(url)
    if url.startswith("//"):
        joined = f"https:{url}"
    elif url.startswith("/"):
        joined = f"https://duckduckgo.com{url}"
    else:
        return None
    parsed = urlparse(joined)
    if parsed.path in {"/l", "/l/"}:
        uddg = parse_qs(parsed.query).get("uddg", [])
        if uddg:
            return html.unescape(uddg[0])
    return joined


def _extract_links(search_html: str, *, require_result_class: bool) -> list[SearchHit]:
    parser = _AnchorParser(require_result_class=require_result_class)
    parser.feed(search_html)
    hits: list[SearchHit] = []
    for raw_url, title in parser.hits:
        if not title:
            continue
        decoded_url = _decode_ddg_redirect(raw_url)
        if decoded_url and (
            decoded_url.startswith("http://") or decoded_url.startswith("https://")
        ):
            hits.append(SearchHit(title=title, url=decoded_url))
    return hits


def _normalize_domain(domain: str) -> str:
    trimmed = domain.strip()
    parsed = urlparse(trimmed)
    candidate = parsed.hostname if parsed.scheme and parsed.hostname else trimmed
    return candidate.strip().lstrip(".").rstrip("/").lower()


def _host_matches(url: str, domains: list[str]) -> bool:
    host = urlparse(url).hostname
    if not host:
        return False
    normalized_host = host.lower()
    for domain in domains:
        normalized = _normalize_domain(domain)
        if normalized and (
            normalized_host == normalized or normalized_host.endswith(f".{normalized}")
        ):
            return True
    return False


def _execute_search(
    query: str,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    search_url = _build_search_url(query)
    response = _requests.get(
        search_url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    hits = _extract_links(response.text, require_result_class=True)
    if not hits:
        hits = _extract_links(response.text, require_result_class=False)
    if allowed_domains is not None:
        hits = [h for h in hits if _host_matches(h.url, allowed_domains)]
    if blocked_domains is not None:
        hits = [h for h in hits if not _host_matches(h.url, blocked_domains)]

    # Deduplicate
    seen: set[str] = set()
    deduped: list[SearchHit] = []
    for h in hits:
        if h.url not in seen:
            seen.add(h.url)
            deduped.append(h)
    hits = deduped[:MAX_RESULTS]

    rendered = "\n".join(f"- [{h.title}]({h.url})" for h in hits)
    if hits:
        summary = f"Search results for {query!r}. Include a Sources section.\n{rendered}"
    else:
        summary = f"No web search results matched the query {query!r}."

    return {
        "query": query,
        "results": [summary, {"content": [h.as_json() for h in hits]}],
        "durationSeconds": time.monotonic() - started,
    }


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for current information and return cited results."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 2},
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional allowlist of domains or URLs. Subdomains match.",
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional blocklist of domains or URLs. Subdomains match.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        query = (input_data.query or "").strip()
        if len(query) < 2:
            return ToolOutput(success=False, result=None, error="Query must be >= 2 characters.")

        allowed = getattr(input_data, "allowed_domains", None)
        blocked = getattr(input_data, "blocked_domains", None)

        try:
            output = await asyncio.to_thread(
                _execute_search, query=query, allowed_domains=allowed, blocked_domains=blocked,
            )
            return ToolOutput(success=True, result=json.dumps(output, indent=2))
        except Exception as exc:
            return ToolOutput(success=False, result=None, error=f"Web search error: {exc}")
