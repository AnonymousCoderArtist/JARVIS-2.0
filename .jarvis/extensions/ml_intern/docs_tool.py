"""Documentation search tools for HF and Gradio docs.

Ported from huggingface/ml-intern agent/tools/docs_tools.py.
Two tools: explore_hf_docs and fetch_hf_docs.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import httpx
from bs4 import BeautifulSoup

from jarvis.api import BaseTool, ToolInput, ToolOutput

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_RESULTS = 20
MAX_RESULTS_CAP = 50

GRADIO_LLMS_TXT_URL = "https://gradio.app/llms.txt"
GRADIO_SEARCH_URL = "https://playground-worker.pages.dev/api/prompt"

COMPOSITE_ENDPOINTS: dict[str, list[str]] = {
    "optimum": ["optimum", "optimum-habana", "optimum-neuron", "optimum-intel", "optimum-executorch", "optimum-tpu"],
    "courses": ["llm-course", "robotics-course", "mcp-course", "smol-course", "agents-course", "deep-rl-course", "computer-vision-course", "audio-course", "ml-games-course", "diffusion-course", "ml-for-3d-course", "cookbook"],
}

DOC_ENDPOINTS = [
    "hub", "transformers", "diffusers", "datasets", "gradio", "trackio", "smolagents",
    "huggingface_hub", "huggingface.js", "transformers.js", "inference-providers",
    "inference-endpoints", "peft", "accelerate", "optimum", "tokenizers", "courses",
    "evaluate", "tasks", "dataset-viewer", "trl", "simulate", "sagemaker", "timm",
    "safetensors", "tgi", "setfit", "lerobot", "autotrain", "tei", "bitsandbytes",
    "sentence_transformers", "chat-ui", "leaderboards", "lighteval", "argilla",
    "distilabel", "microsoft-azure", "kernels", "google-cloud",
]

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

_docs_cache: dict[str, list[dict[str, str]]] = {}
_index_cache: dict[str, tuple[Any, Any]] = {}
_cache_lock = asyncio.Lock()

# Whoosh is optional — search degrades gracefully without it
_whoosh_available = False
try:
    from whoosh.analysis import StemmingAnalyzer
    from whoosh.fields import ID, TEXT, Schema
    from whoosh.filedb.filestore import RamStorage
    from whoosh.qparser import MultifieldParser, OrGroup
    _whoosh_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Gradio Documentation
# ---------------------------------------------------------------------------

async def _fetch_gradio_docs(query: str | None = None) -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        if not query:
            resp = await client.get(GRADIO_LLMS_TXT_URL)
            resp.raise_for_status()
            return resp.text
        resp = await client.post(
            GRADIO_SEARCH_URL,
            headers={"Content-Type": "application/json", "Origin": "https://gradio-docs-mcp.up.railway.app"},
            json={"prompt_to_embed": query, "SYSTEM_PROMPT": "$INSERT_GUIDES_DOCS_DEMOS", "FALLBACK_PROMPT": "No results found"},
        )
        resp.raise_for_status()
        return resp.json().get("SYS_PROMPT", "No results found")


# ---------------------------------------------------------------------------
# HF Documentation
# ---------------------------------------------------------------------------

async def _fetch_endpoint_docs(hf_token: str, endpoint: str) -> list[dict[str, str]]:
    url = f"https://huggingface.co/docs/{endpoint}"
    headers = {"Authorization": f"Bearer {hf_token}"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        sidebar = soup.find("nav", class_=lambda x: bool(x and "flex-auto" in x))
        if not sidebar:
            raise ValueError(f"Could not find navigation sidebar for '{endpoint}'")
        nav_items = []
        for link in sidebar.find_all("a", href=True):
            href = cast(str, link["href"])
            page_url = f"https://huggingface.co{href}" if href.startswith("/") else href
            nav_items.append({"title": link.get_text(strip=True), "url": page_url})
        if not nav_items:
            raise ValueError(f"No navigation links found for '{endpoint}'")

        async def fetch_page(item: dict[str, str]) -> dict[str, str]:
            md_url = f"{item['url']}.md"
            try:
                r = await client.get(md_url, headers=headers)
                r.raise_for_status()
                content = r.text.strip()
                glimpse = content[:200] + "..." if len(content) > 200 else content
            except Exception as e:
                content, glimpse = "", f"[Could not fetch: {str(e)[:50]}]"
            return {"title": item["title"], "url": item["url"], "md_url": md_url, "glimpse": glimpse, "content": content, "section": endpoint}

        return list(await asyncio.gather(*[fetch_page(item) for item in nav_items]))


async def _get_docs(hf_token: str, endpoint: str) -> list[dict[str, str]]:
    async with _cache_lock:
        if endpoint in _docs_cache:
            return _docs_cache[endpoint]
    sub_endpoints = COMPOSITE_ENDPOINTS.get(endpoint, [endpoint])
    all_docs: list[dict[str, str]] = []
    for sub in sub_endpoints:
        async with _cache_lock:
            if sub in _docs_cache:
                all_docs.extend(_docs_cache[sub])
                continue
        docs = await _fetch_endpoint_docs(hf_token, sub)
        async with _cache_lock:
            _docs_cache[sub] = docs
        all_docs.extend(docs)
    async with _cache_lock:
        _docs_cache[endpoint] = all_docs
    return all_docs


async def _build_search_index(endpoint: str, docs: list[dict[str, str]]) -> tuple[Any, Any]:
    if not _whoosh_available:
        raise RuntimeError("Whoosh not installed — search unavailable")
    async with _cache_lock:
        if endpoint in _index_cache:
            return _index_cache[endpoint]
    analyzer = StemmingAnalyzer()
    schema = Schema(title=TEXT(stored=True, analyzer=analyzer), url=ID(stored=True, unique=True), md_url=ID(stored=True), section=ID(stored=True), glimpse=TEXT(stored=True, analyzer=analyzer), content=TEXT(stored=False, analyzer=analyzer))
    storage = RamStorage()
    index = storage.create_index(schema)
    writer = index.writer()
    for doc in docs:
        writer.add_document(title=doc.get("title", ""), url=doc.get("url", ""), md_url=doc.get("md_url", ""), section=doc.get("section", endpoint), glimpse=doc.get("glimpse", ""), content=doc.get("content", ""))
    writer.commit()
    parser = MultifieldParser(["title", "content"], schema=schema, fieldboosts={"title": 2.0, "content": 1.0}, group=OrGroup)
    async with _cache_lock:
        _index_cache[endpoint] = (index, parser)
    return index, parser


async def _search_docs(endpoint: str, docs: list[dict[str, str]], query: str, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    index, parser = await _build_search_index(endpoint, docs)
    try:
        query_obj = parser.parse(query)
    except Exception:
        return [], "Query contained unsupported syntax; showing default ordering."
    with index.searcher() as searcher:
        results = searcher.search(query_obj, limit=limit)
        matches = [{"title": hit["title"], "url": hit["url"], "md_url": hit.get("md_url", ""), "section": hit.get("section", endpoint), "glimpse": hit["glimpse"], "score": round(hit.score, 2)} for hit in results]
    if not matches:
        return [], "No strong matches found; showing default ordering."
    return matches, None


def _format_results(endpoint: str, items: list[dict[str, Any]], total: int, query: str | None = None, note: str | None = None) -> str:
    base_url = f"https://huggingface.co/docs/{endpoint}"
    out = f"Documentation structure for: {base_url}\n\n"
    if query:
        out += f"Query: '{query}' → showing {len(items)} result(s) out of {total} pages"
        if note:
            out += f" ({note})"
        out += "\n\n"
    else:
        out += f"Found {len(items)} page(s) (total available: {total}).\n"
        if note:
            out += f"({note})\n"
        out += "\n"
    for i, item in enumerate(items, 1):
        out += f"{i}. **{item['title']}**\n"
        out += f"   URL: {item['url']}\n"
        out += f"   Section: {item.get('section', endpoint)}\n"
        if query and "score" in item:
            out += f"   Relevance score: {item['score']:.2f}\n"
        out += f"   Glimpse: {item['glimpse']}\n\n"
    return out


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class ExploreHfDocsTool(BaseTool):
    name = "explore_hf_docs"
    description = (
        "Browse HF documentation structure — discover all available documentation with 200-char previews.\n\n"
        "Use this to find relevant documentation and/or examples with detailed parameter docs and API reference. "
        "To be used together with github_find_examples and github_read_file to find working examples and documentation.\n\n"
        "Pattern: explore_hf_docs (find relevant pages) → fetch_hf_docs (get full content).\n\n"
        "For training tasks: fetch the trainer config docs (SFTConfig, DPOConfig, GRPOConfig) to verify parameter names. "
        "Returns top 20 results by default; set max_results (max 50) to adjust."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "enum": DOC_ENDPOINTS,
                "description": "The documentation endpoint to explore.",
            },
            "query": {
                "type": "string",
                "description": "Optional keyword query to rank and filter documentation pages.",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results (default 20, max 50). Ignored for Gradio.",
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["endpoint"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        endpoint = (input_data.query or getattr(input_data, "endpoint", "") or "").lstrip("/")
        query = getattr(input_data, "query", None)
        max_results = getattr(input_data, "max_results", None)

        # Fix: endpoint comes from the endpoint field, not query
        endpoint_raw = getattr(input_data, "endpoint", None)
        if endpoint_raw:
            endpoint = endpoint_raw.lstrip("/")

        if not endpoint:
            return ToolOutput(success=False, result=None, error="No endpoint provided")

        if endpoint.lower() == "gradio":
            try:
                clean_query = query.strip() if isinstance(query, str) and query.strip() else None
                content = await _fetch_gradio_docs(clean_query)
                header = "# Gradio Documentation\n\n"
                if clean_query:
                    header += f"Query: '{clean_query}'\n\n"
                header += "Source: https://gradio.app/docs\n\n---\n\n"
                return ToolOutput(success=True, result=header + content)
            except Exception as e:
                return ToolOutput(success=False, result=None, error=f"Error fetching Gradio docs: {e}")

        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return ToolOutput(success=False, result=None, error="No HF_TOKEN available (not logged in)")

        try:
            max_results_int = int(max_results) if max_results is not None else None
        except (TypeError, ValueError):
            return ToolOutput(success=False, result=None, error="max_results must be an integer")

        if max_results_int is not None and max_results_int <= 0:
            return ToolOutput(success=False, result=None, error="max_results must be greater than zero")

        try:
            docs = await _get_docs(hf_token, endpoint)
            total = len(docs)
            if max_results_int is None:
                limit = DEFAULT_MAX_RESULTS
                limit_note = f"Showing top {DEFAULT_MAX_RESULTS} results (set max_results to adjust)."
            elif max_results_int > MAX_RESULTS_CAP:
                limit = MAX_RESULTS_CAP
                limit_note = f"Requested {max_results_int} but showing top {MAX_RESULTS_CAP} (maximum)."
            else:
                limit = max_results_int
                limit_note = None

            clean_query = query.strip() if isinstance(query, str) and query.strip() else None
            fallback_msg = None

            if clean_query:
                try:
                    results, fallback_msg = await _search_docs(endpoint, docs, clean_query, limit)
                except RuntimeError:
                    results = docs[:limit]
                    fallback_msg = "Whoosh not installed; showing default ordering."
                if not results:
                    results = docs[:limit]
            else:
                results = docs[:limit]

            notes = []
            if fallback_msg:
                notes.append(fallback_msg)
            if limit_note:
                notes.append(limit_note)
            note = "; ".join(notes) if notes else None

            return ToolOutput(success=True, result=_format_results(endpoint, results, total, clean_query, note))
        except httpx.HTTPStatusError as e:
            return ToolOutput(success=False, result=None, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")


class FetchHfDocsTool(BaseTool):
    name = "fetch_hf_docs"
    description = (
        "Fetch full markdown content of an HF documentation page. Use after explore_hf_docs.\n\n"
        "Critical for finding documentation e.g. current trainer configuration parameters (SFTConfig, DPOConfig, etc.) "
        "Use for researching solutions and before writing training scripts. Your internal knowledge is outdated.\n\n"
        "Provide the full URL from explore_hf_docs results. The .md extension is added automatically."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to the documentation page. Example: 'https://huggingface.co/docs/trl/dpo_trainer'",
            },
        },
        "required": ["url"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        url = input_data.query or ""
        if not url:
            return ToolOutput(success=False, result=None, error="No URL provided")

        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return ToolOutput(success=False, result=None, error="No HF_TOKEN available (not logged in)")

        if not url.endswith(".md"):
            url = f"{url}.md"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {hf_token}"})
                resp.raise_for_status()
            return ToolOutput(success=True, result=f"Documentation from: {url}\n\n{resp.text}")
        except httpx.HTTPStatusError as e:
            return ToolOutput(success=False, result=None, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error fetching documentation: {e}")


# Need os for HF_TOKEN
import os  # noqa: E402
