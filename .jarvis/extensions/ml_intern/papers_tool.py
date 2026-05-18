"""HF Papers tool — discover papers, read contents, find linked resources.

Ported from huggingface/ml-intern agent/tools/papers_tool.py.
Operations: trending, search, paper_details, read_paper, citation_graph,
            snippet_search, recommend, find_datasets, find_models,
            find_collections, find_all_resources.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag
from typing import cast

from jarvis.api import BaseTool, ToolInput, ToolOutput

HF_API = "https://huggingface.co/api"
ARXIV_HTML = "https://arxiv.org/html"
AR5IV_HTML = "https://ar5iv.labs.arxiv.org/html"

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_SUMMARY_LEN = 300
MAX_SECTION_PREVIEW_LEN = 280
MAX_SECTION_TEXT_LEN = 8000

SORT_MAP = {"downloads": "downloads", "likes": "likes", "trending": "trendingScore"}

# Semantic Scholar
S2_API = "https://api.semanticscholar.org"
S2_API_KEY = os.environ.get("S2_API_KEY")
S2_HEADERS: dict[str, str] = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
S2_TIMEOUT = 12
_s2_last_request: float = 0.0
_s2_cache: dict[str, Any] = {}
_S2_CACHE_MAX = 500


# ---------------------------------------------------------------------------
# S2 helpers
# ---------------------------------------------------------------------------

def _s2_paper_id(arxiv_id: str) -> str:
    return f"ARXIV:{arxiv_id}"


def _s2_cache_key(path: str, params: dict | None) -> str:
    p = tuple(sorted((params or {}).items()))
    return f"{path}:{p}"


async def _s2_request(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
    global _s2_last_request
    url = f"{S2_API}{path}"
    kwargs.setdefault("headers", {}).update(S2_HEADERS)
    kwargs.setdefault("timeout", S2_TIMEOUT)
    for attempt in range(3):
        if S2_API_KEY:
            min_interval = 1.0 if "search" in path else 0.1
            elapsed = time.monotonic() - _s2_last_request
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
        _s2_last_request = time.monotonic()
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429 and attempt < 2:
                await asyncio.sleep(60)
                continue
            if resp.status_code >= 500 and attempt < 2:
                await asyncio.sleep(3)
                continue
            return resp
        except (httpx.RequestError, httpx.HTTPStatusError):
            if attempt < 2:
                await asyncio.sleep(3)
                continue
            return None
    return None


async def _s2_get_json(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict | None:
    key = _s2_cache_key(path, params)
    if key in _s2_cache:
        return _s2_cache[key]
    resp = await _s2_request(client, "GET", path, params=params or {})
    if resp and resp.status_code == 200:
        data = resp.json()
        if len(_s2_cache) < _S2_CACHE_MAX:
            _s2_cache[key] = data
        return data
    return None


# ---------------------------------------------------------------------------
# HTML paper parsing
# ---------------------------------------------------------------------------

def _parse_paper_html(html_text: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    title_el = soup.find("h1", class_="ltx_title")
    title = title_el.get_text(strip=True).removeprefix("Title:") if title_el else ""
    abstract_el = soup.find("div", class_="ltx_abstract")
    abstract = ""
    if abstract_el:
        for child in abstract_el.children:
            if isinstance(child, Tag) and child.name in ("h6", "h2", "h3", "p", "span"):
                if child.get_text(strip=True).lower() == "abstract":
                    continue
            if isinstance(child, Tag) and child.name == "p":
                abstract += child.get_text(separator=" ", strip=True) + " "
        abstract = abstract.strip()
    sections: list[dict[str, Any]] = []
    headings = soup.find_all(["h2", "h3"], class_=lambda c: c and "ltx_title" in c)
    for heading in headings:
        level = 2 if heading.name == "h2" else 3
        heading_text = heading.get_text(separator=" ", strip=True)
        text_parts: list[str] = []
        sibling = heading.find_next_sibling()
        while sibling:
            if isinstance(sibling, Tag):
                if sibling.name in ("h2", "h3") and "ltx_title" in (sibling.get("class") or []):
                    break
                if sibling.name == "h2" and level == 3:
                    break
                text_parts.append(sibling.get_text(separator=" ", strip=True))
            sibling = sibling.find_next_sibling()
        parent_section = heading.find_parent("section")
        if parent_section and not text_parts:
            for p in parent_section.find_all("p", recursive=False):
                text_parts.append(p.get_text(separator=" ", strip=True))
        section_text = "\n\n".join(t for t in text_parts if t)
        num_match = re.match(r"^([A-Z]?\d+(?:\.\d+)*)\s", heading_text)
        section_id = num_match.group(1) if num_match else ""
        sections.append({"id": section_id, "title": heading_text, "level": level, "text": section_text})
    return {"title": title, "abstract": abstract, "sections": sections}


def _find_section(sections: list[dict], query: str) -> dict | None:
    q = query.lower().strip()
    for s in sections:
        if s["id"] == q or s["id"] == query:
            return s
    for s in sections:
        if q == s["title"].lower():
            return s
    for s in sections:
        if q in s["title"].lower():
            return s
    for s in sections:
        if s["id"].startswith(q + ".") or s["id"] == q:
            return s
    return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + "..."


def _clean_description(text: str) -> str:
    text = re.sub(r"[\t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _format_paper_list(papers: list, title: str, date: str | None = None, query: str | None = None) -> str:
    lines = [f"# {title}"]
    if date:
        lines[0] += f" ({date})"
    if query:
        lines.append(f"Filtered by: '{query}'")
    lines.append(f"Showing {len(papers)} paper(s)\n")
    for i, item in enumerate(papers, 1):
        paper = item.get("paper", item)
        aid = paper.get("id", "")
        ptitle = paper.get("title", "Unknown")
        upvotes = paper.get("upvotes", 0)
        summary = paper.get("ai_summary") or _truncate(paper.get("summary", ""), MAX_SUMMARY_LEN)
        keywords = paper.get("ai_keywords") or []
        github = paper.get("githubRepo") or ""
        stars = paper.get("githubStars") or 0
        lines.append(f"## {i}. {ptitle}")
        lines.append(f"**arxiv_id:** {aid} | **upvotes:** {upvotes}")
        lines.append(f"https://huggingface.co/papers/{aid}")
        if keywords:
            lines.append(f"**Keywords:** {', '.join(keywords[:5])}")
        if github:
            lines.append(f"**GitHub:** {github} ({stars} stars)")
        if summary:
            lines.append(f"**Summary:** {_truncate(summary, MAX_SUMMARY_LEN)}")
        lines.append("")
    return "\n".join(lines)


def _format_paper_detail(paper: dict, s2_data: dict | None = None) -> str:
    aid = paper.get("id", "")
    title = paper.get("title", "Unknown")
    upvotes = paper.get("upvotes", 0)
    ai_summary = paper.get("ai_summary") or ""
    summary = paper.get("summary", "")
    keywords = paper.get("ai_keywords") or []
    github = paper.get("githubRepo") or ""
    stars = paper.get("githubStars") or 0
    authors = paper.get("authors") or []
    lines = [f"# {title}"]
    meta = [f"**arxiv_id:** {aid}", f"**upvotes:** {upvotes}"]
    if s2_data:
        meta.append(f"**citations:** {s2_data.get('citationCount', 0)} ({s2_data.get('influentialCitationCount', 0)} influential)")
    lines.append(" | ".join(meta))
    lines.append(f"https://huggingface.co/papers/{aid}")
    lines.append(f"https://arxiv.org/abs/{aid}")
    if authors:
        names = [a.get("name", "") for a in authors[:10]]
        lines.append(f"**Authors:** {', '.join(n for n in names if n)}")
    if keywords:
        lines.append(f"**Keywords:** {', '.join(keywords)}")
    if github:
        lines.append(f"**GitHub:** {github} ({stars} stars)")
    if s2_data and s2_data.get("tldr"):
        lines.append(f"\n## TL;DR\n{s2_data['tldr'].get('text', '')}")
    if ai_summary:
        lines.append(f"\n## AI Summary\n{ai_summary}")
    if summary:
        lines.append(f"\n## Abstract\n{_truncate(summary, 500)}")
    lines.append("\n**Next:** Use read_paper to read specific sections, find_all_resources for linked datasets/models, or citation_graph to trace references and citations.")
    return "\n".join(lines)


def _format_read_paper_toc(parsed: dict[str, Any], aid: str) -> str:
    lines = [f"# {parsed['title']}", f"https://arxiv.org/abs/{aid}\n"]
    if parsed["abstract"]:
        lines.append(f"## Abstract\n{parsed['abstract']}\n")
    lines.append("## Sections")
    for s in parsed["sections"]:
        prefix = "  " if s["level"] == 3 else ""
        preview = _truncate(s["text"], MAX_SECTION_PREVIEW_LEN) if s["text"] else "(empty)"
        lines.append(f"{prefix}- **{s['title']}**: {preview}")
    lines.append('\nCall read_paper with section parameter (e.g. section="4" or section="Experiments") to read a specific section.')
    return "\n".join(lines)


def _format_read_paper_section(section: dict, aid: str) -> str:
    lines = [f"# {section['title']}", f"https://arxiv.org/abs/{aid}\n"]
    text = section["text"]
    if len(text) > MAX_SECTION_TEXT_LEN:
        text = text[:MAX_SECTION_TEXT_LEN] + f"\n\n... (truncated at {MAX_SECTION_TEXT_LEN} chars)"
    lines.append(text if text else "(This section has no extractable text content.)")
    return "\n".join(lines)


def _format_datasets(datasets: list, aid: str, sort: str) -> str:
    lines = [f"# Datasets linked to paper {aid}", f"https://huggingface.co/papers/{aid}", f"Showing {len(datasets)} dataset(s), sorted by {sort}\n"]
    for i, ds in enumerate(datasets, 1):
        ds_id = ds.get("id", "unknown")
        downloads = ds.get("downloads", 0)
        likes = ds.get("likes", 0)
        desc = _truncate(_clean_description(ds.get("description") or ""), MAX_SUMMARY_LEN)
        lines.append(f"**{i}. [{ds_id}](https://huggingface.co/datasets/{ds_id})**")
        lines.append(f"   Downloads: {downloads:,} | Likes: {likes}")
        if desc:
            lines.append(f"   {desc}")
        lines.append("")
    if datasets:
        top = datasets[0].get("id", "")
        lines.append(f'**Inspect top dataset:** hf_inspect_dataset(dataset="{top}")')
    return "\n".join(lines)


def _format_models(models: list, aid: str, sort: str) -> str:
    lines = [f"# Models linked to paper {aid}", f"https://huggingface.co/papers/{aid}", f"Showing {len(models)} model(s), sorted by {sort}\n"]
    for i, m in enumerate(models, 1):
        mid = m.get("id", "unknown")
        downloads = m.get("downloads", 0)
        likes = m.get("likes", 0)
        pipeline = m.get("pipeline_tag") or ""
        lines.append(f"**{i}. [{mid}](https://huggingface.co/{mid})**")
        meta = f"   Downloads: {downloads:,} | Likes: {likes}"
        if pipeline:
            meta += f" | Task: {pipeline}"
        lines.append(meta)
        lines.append("")
    return "\n".join(lines)


def _format_collections(collections: list, aid: str) -> str:
    lines = [f"# Collections containing paper {aid}", f"Showing {len(collections)} collection(s)\n"]
    for i, c in enumerate(collections, 1):
        slug = c.get("slug", "")
        ctitle = c.get("title", "Untitled")
        owner = c.get("owner", {}).get("name", "")
        upvotes = c.get("upvotes", 0)
        lines.append(f"**{i}. {ctitle}**")
        lines.append(f"   By: {owner} | Upvotes: {upvotes}")
        lines.append(f"   https://huggingface.co/collections/{slug}")
        lines.append("")
    return "\n".join(lines)


def _format_datasets_compact(datasets: list) -> str:
    if not datasets:
        return "## Datasets\nNone found"
    lines = [f"## Datasets ({len(datasets)})"]
    for ds in datasets:
        lines.append(f"- **{ds.get('id', '?')}** ({ds.get('downloads', 0):,} downloads)")
    return "\n".join(lines)


def _format_models_compact(models: list) -> str:
    if not models:
        return "## Models\nNone found"
    lines = [f"## Models ({len(models)})"]
    for m in models:
        pipeline = m.get("pipeline_tag") or ""
        suffix = f" ({pipeline})" if pipeline else ""
        lines.append(f"- **{m.get('id', '?')}** ({m.get('downloads', 0):,} downloads){suffix}")
    return "\n".join(lines)


def _format_collections_compact(collections: list) -> str:
    if not collections:
        return "## Collections\nNone found"
    lines = [f"## Collections ({len(collections)})"]
    for c in collections:
        lines.append(f"- **{c.get('title', 'Untitled')}** by {c.get('owner', {}).get('name', '')} ({c.get('upvotes', 0)} upvotes)")
    return "\n".join(lines)


def _format_citation_entry(entry: dict, show_context: bool = False) -> str:
    paper = entry.get("citingPaper") or entry.get("citedPaper") or {}
    title = paper.get("title") or "(untitled)"
    year = paper.get("year") or "?"
    cites = paper.get("citationCount", 0)
    ext_ids = paper.get("externalIds") or {}
    aid = ext_ids.get("ArXiv", "")
    influential = " **[influential]**" if entry.get("isInfluential") else ""
    parts = [f"- **{title}** ({year}, {cites} cites){influential}"]
    if aid:
        parts[0] += f"  arxiv:{aid}"
    if show_context:
        intents = entry.get("intents") or []
        if intents:
            parts.append(f"  Intent: {', '.join(intents)}")
        contexts = entry.get("contexts") or []
        for ctx in contexts[:2]:
            if ctx:
                parts.append(f"  > {_truncate(ctx, 200)}")
    return "\n".join(parts)


def _format_citation_graph(aid: str, references: list[dict] | None, citations: list[dict] | None) -> str:
    lines = [f"# Citation Graph for {aid}", f"https://arxiv.org/abs/{aid}\n"]
    if references is not None:
        lines.append(f"## References ({len(references)})")
        if references:
            for entry in references:
                lines.append(_format_citation_entry(entry))
        else:
            lines.append("No references found.")
        lines.append("")
    if citations is not None:
        lines.append(f"## Citations ({len(citations)})")
        if citations:
            for entry in citations:
                lines.append(_format_citation_entry(entry, show_context=True))
        else:
            lines.append("No citations found.")
        lines.append("")
    lines.append("**Tip:** Use paper_details with an arxiv_id from above to explore further.")
    return "\n".join(lines)


def _format_s2_paper_list(papers: list[dict], title: str) -> str:
    lines = [f"# {title}", f"Showing {len(papers)} result(s)\n"]
    for i, paper in enumerate(papers, 1):
        ptitle = paper.get("title") or "(untitled)"
        year = paper.get("year") or "?"
        cites = paper.get("citationCount", 0)
        venue = paper.get("venue") or ""
        ext_ids = paper.get("externalIds") or {}
        aid = ext_ids.get("ArXiv", "")
        tldr = (paper.get("tldr") or {}).get("text", "")
        lines.append(f"### {i}. {ptitle}")
        meta = [f"Year: {year}", f"Citations: {cites}"]
        if venue:
            meta.append(f"Venue: {venue}")
        if aid:
            meta.append(f"arxiv_id: {aid}")
        lines.append(" | ".join(meta))
        if aid:
            lines.append(f"https://arxiv.org/abs/{aid}")
        if tldr:
            lines.append(f"**TL;DR:** {tldr}")
        lines.append("")
    lines.append("Use paper_details with arxiv_id for full info, or read_paper to read sections.")
    return "\n".join(lines)


def _format_snippets(snippets: list[dict], query: str) -> str:
    lines = [f"# Snippet Search: '{query}'", f"Found {len(snippets)} matching passage(s)\n"]
    for i, item in enumerate(snippets, 1):
        paper = item.get("paper") or {}
        ptitle = paper.get("title") or "(untitled)"
        year = paper.get("year") or "?"
        cites = paper.get("citationCount", 0)
        ext_ids = paper.get("externalIds") or {}
        aid = ext_ids.get("ArXiv", "")
        snippet = item.get("snippet") or {}
        text = snippet.get("text", "")
        section = snippet.get("section") or ""
        lines.append(f"### {i}. {ptitle} ({year}, {cites} cites)")
        if aid:
            lines.append(f"arxiv:{aid}")
        if section:
            lines.append(f"Section: {section}")
        if text:
            lines.append(f"> {_truncate(text, 400)}")
        lines.append("")
    lines.append("Use paper_details or read_paper with arxiv_id to explore a paper further.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------

def _error(message: str) -> dict:
    return {"formatted": message, "totalResults": 0, "resultsShared": 0, "isError": True}


async def _op_trending(args: dict[str, Any], limit: int) -> dict:
    date = args.get("date")
    query = args.get("query")
    params: dict[str, Any] = {"limit": limit if not query else max(limit * 3, 30)}
    if date:
        params["date"] = date
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/daily_papers", params=params)
        resp.raise_for_status()
        papers = resp.json()
    if query:
        q = query.lower()
        papers = [p for p in papers if q in p.get("title", "").lower() or q in p.get("paper", {}).get("title", "").lower() or q in p.get("paper", {}).get("summary", "").lower() or any(q in kw.lower() for kw in (p.get("paper", {}).get("ai_keywords") or []))]
    papers = papers[:limit]
    if not papers:
        msg = "No trending papers found"
        if query:
            msg += f" matching '{query}'"
        if date:
            msg += f" for {date}"
        return {"formatted": msg, "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_paper_list(papers, "Trending Papers", date=date, query=query), "totalResults": len(papers), "resultsShared": len(papers)}


async def _s2_bulk_search(query: str, args: dict[str, Any], limit: int) -> dict | None:
    params: dict[str, Any] = {"query": query, "limit": limit, "fields": "title,externalIds,year,citationCount,tldr,venue,publicationDate"}
    date_from = args.get("date_from", "")
    date_to = args.get("date_to", "")
    if date_from or date_to:
        params["publicationDateOrYear"] = f"{date_from}:{date_to}"
    if args.get("categories"):
        params["fieldsOfStudy"] = args["categories"]
    if args.get("min_citations"):
        params["minCitationCount"] = str(args["min_citations"])
    sort_by = args.get("sort_by")
    if sort_by and sort_by != "relevance":
        params["sort"] = f"{sort_by}:desc"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await _s2_request(client, "GET", "/graph/v1/paper/search/bulk", params=params)
        if not resp or resp.status_code != 200:
            return None
        data = resp.json()
    papers = data.get("data") or []
    if not papers:
        return {"formatted": f"No papers found for '{query}' with the given filters.", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_s2_paper_list(papers[:limit], f"Papers matching '{query}' (Semantic Scholar)"), "totalResults": data.get("total", len(papers)), "resultsShared": min(limit, len(papers))}


async def _op_search(args: dict[str, Any], limit: int) -> dict:
    query = args.get("query")
    if not query:
        return _error("'query' is required for search operation.")
    use_s2 = any(args.get(k) for k in ("date_from", "date_to", "categories", "min_citations", "sort_by"))
    if use_s2:
        result = await _s2_bulk_search(query, args, limit)
        if result is not None:
            return result
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/papers/search", params={"q": query, "limit": limit})
        resp.raise_for_status()
        papers = resp.json()
    if not papers:
        return {"formatted": f"No papers found for '{query}'", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_paper_list(papers, f"Papers matching '{query}'"), "totalResults": len(papers), "resultsShared": len(papers)}


async def _op_paper_details(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for paper_details.")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/papers/{aid}")
        resp.raise_for_status()
        paper = resp.json()
    return {"formatted": _format_paper_detail(paper), "totalResults": 1, "resultsShared": 1}


async def _op_read_paper(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for read_paper.")
    section_query = args.get("section")
    parsed = None
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for base_url in [ARXIV_HTML, AR5IV_HTML]:
            try:
                resp = await client.get(f"{base_url}/{aid}")
                if resp.status_code == 200:
                    parsed = _parse_paper_html(resp.text)
                    if parsed["sections"]:
                        break
                    parsed = None
            except httpx.RequestError:
                continue
    if not parsed or not parsed["sections"]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{HF_API}/papers/{aid}")
                resp.raise_for_status()
                paper = resp.json()
            abstract = paper.get("summary", "")
            ptitle = paper.get("title", "")
            msg = f"# {ptitle}\nhttps://arxiv.org/abs/{aid}\n\n## Abstract\n{abstract}\n\nHTML version not available. Only abstract shown.\nPDF: https://arxiv.org/pdf/{aid}"
            return {"formatted": msg, "totalResults": 1, "resultsShared": 1}
        except Exception:
            return _error(f"Could not fetch paper {aid}. Check the arxiv ID is correct.")
    if not section_query:
        return {"formatted": _format_read_paper_toc(parsed, aid), "totalResults": len(parsed["sections"]), "resultsShared": len(parsed["sections"])}
    section = _find_section(parsed["sections"], section_query)
    if not section:
        available = "\n".join(f"- {s['title']}" for s in parsed["sections"])
        return _error(f"Section '{section_query}' not found. Available sections:\n{available}")
    return {"formatted": _format_read_paper_section(section, aid), "totalResults": 1, "resultsShared": 1}


async def _op_citation_graph(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for citation_graph.")
    direction = args.get("direction", "both")
    s2_id = _s2_paper_id(aid)
    fields = "title,externalIds,year,citationCount,influentialCitationCount,contexts,intents,isInfluential"
    params = {"fields": fields, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        refs, cites = None, None
        coros = []
        if direction in ("references", "both"):
            coros.append(_s2_get_json(client, f"/graph/v1/paper/{s2_id}/references", params))
        if direction in ("citations", "both"):
            coros.append(_s2_get_json(client, f"/graph/v1/paper/{s2_id}/citations", params))
        results = await asyncio.gather(*coros, return_exceptions=True)
        idx = 0
        if direction in ("references", "both"):
            r = results[idx]
            if isinstance(r, dict):
                refs = r.get("data", [])
            idx += 1
        if direction in ("citations", "both"):
            r = results[idx]
            if isinstance(r, dict):
                cites = r.get("data", [])
    if refs is None and cites is None:
        return _error(f"Could not fetch citation data for {aid}. Paper may not be indexed by Semantic Scholar.")
    total = (len(refs) if refs else 0) + (len(cites) if cites else 0)
    return {"formatted": _format_citation_graph(aid, refs, cites), "totalResults": total, "resultsShared": total}


async def _op_find_datasets(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for find_datasets.")
    sort = args.get("sort", "downloads")
    sort_key = SORT_MAP.get(sort, "downloads")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/datasets", params={"filter": f"arxiv:{aid}", "limit": limit, "sort": sort_key, "direction": -1})
        resp.raise_for_status()
        datasets = resp.json()
    if not datasets:
        return {"formatted": f"No datasets found linked to paper {aid}.\nhttps://huggingface.co/papers/{aid}", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_datasets(datasets, aid, sort), "totalResults": len(datasets), "resultsShared": len(datasets)}


async def _op_find_models(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for find_models.")
    sort = args.get("sort", "downloads")
    sort_key = SORT_MAP.get(sort, "downloads")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/models", params={"filter": f"arxiv:{aid}", "limit": limit, "sort": sort_key, "direction": -1})
        resp.raise_for_status()
        models = resp.json()
    if not models:
        return {"formatted": f"No models found linked to paper {aid}.\nhttps://huggingface.co/papers/{aid}", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_models(models, aid, sort), "totalResults": len(models), "resultsShared": len(models)}


async def _op_find_collections(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for find_collections.")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HF_API}/collections", params={"paper": aid})
        resp.raise_for_status()
        collections = resp.json()
    if not collections:
        return {"formatted": f"No collections found containing paper {aid}.\nhttps://huggingface.co/papers/{aid}", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_collections(collections[:limit], aid), "totalResults": len(collections[:limit]), "resultsShared": len(collections[:limit])}


async def _op_find_all_resources(args: dict[str, Any], limit: int) -> dict:
    aid = args.get("arxiv_id")
    if not aid:
        return _error("'arxiv_id' is required for find_all_resources.")
    per_cat = min(limit, 10)
    async with httpx.AsyncClient(timeout=15) as client:
        results = await asyncio.gather(
            client.get(f"{HF_API}/datasets", params={"filter": f"arxiv:{aid}", "limit": per_cat, "sort": "downloads", "direction": -1}),
            client.get(f"{HF_API}/models", params={"filter": f"arxiv:{aid}", "limit": per_cat, "sort": "downloads", "direction": -1}),
            client.get(f"{HF_API}/collections", params={"paper": aid}),
            return_exceptions=True,
        )
    sections = []
    total = 0
    if isinstance(results[0], Exception):
        sections.append(f"## Datasets\nError: {results[0]}")
    else:
        datasets = cast(httpx.Response, results[0]).json()
        total += len(datasets)
        sections.append(_format_datasets_compact(datasets[:per_cat]))
    if isinstance(results[1], Exception):
        sections.append(f"## Models\nError: {results[1]}")
    else:
        models = cast(httpx.Response, results[1]).json()
        total += len(models)
        sections.append(_format_models_compact(models[:per_cat]))
    if isinstance(results[2], Exception):
        sections.append(f"## Collections\nError: {results[2]}")
    else:
        collections = cast(httpx.Response, results[2]).json()
        total += len(collections)
        sections.append(_format_collections_compact(collections[:per_cat]))
    header = f"# Resources linked to paper {aid}\nhttps://huggingface.co/papers/{aid}\n"
    return {"formatted": header + "\n\n".join(sections), "totalResults": total, "resultsShared": total}


async def _op_snippet_search(args: dict[str, Any], limit: int) -> dict:
    query = args.get("query")
    if not query:
        return _error("'query' is required for snippet_search.")
    params: dict[str, Any] = {"query": query, "limit": limit, "fields": "title,externalIds,year,citationCount"}
    date_from = args.get("date_from", "")
    date_to = args.get("date_to", "")
    if date_from or date_to:
        params["publicationDateOrYear"] = f"{date_from}:{date_to}"
    if args.get("categories"):
        params["fieldsOfStudy"] = args["categories"]
    if args.get("min_citations"):
        params["minCitationCount"] = str(args["min_citations"])
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await _s2_request(client, "GET", "/graph/v1/snippet/search", params=params)
        if not resp or resp.status_code != 200:
            return _error("Snippet search failed. Semantic Scholar may be unavailable.")
        data = resp.json()
    snippets = data.get("data") or []
    if not snippets:
        return {"formatted": f"No snippets found for '{query}'.", "totalResults": 0, "resultsShared": 0}
    return {"formatted": _format_snippets(snippets, query), "totalResults": len(snippets), "resultsShared": len(snippets)}


async def _op_recommend(args: dict[str, Any], limit: int) -> dict:
    positive_ids = args.get("positive_ids")
    aid = args.get("arxiv_id")
    if not aid and not positive_ids:
        return _error("'arxiv_id' or 'positive_ids' is required for recommend.")
    fields = "title,externalIds,year,citationCount,tldr,venue"
    async with httpx.AsyncClient(timeout=15) as client:
        if positive_ids and not aid:
            pos = [_s2_paper_id(pid.strip()) for pid in positive_ids.split(",") if pid.strip()]
            neg_raw = args.get("negative_ids", "")
            neg = [_s2_paper_id(pid.strip()) for pid in neg_raw.split(",") if pid.strip()] if neg_raw else []
            resp = await _s2_request(client, "POST", "/recommendations/v1/papers/", json={"positivePaperIds": pos, "negativePaperIds": neg}, params={"fields": fields, "limit": limit})
            if not resp or resp.status_code != 200:
                return _error("Recommendation request failed. Semantic Scholar may be unavailable.")
            data = resp.json()
        else:
            if not aid:
                return _error("'arxiv_id' is required for recommend.")
            data = await _s2_get_json(client, f"/recommendations/v1/papers/forpaper/{_s2_paper_id(aid)}", {"fields": fields, "limit": limit, "from": "recent"})
            if not data:
                return _error("Recommendation request failed. Semantic Scholar may be unavailable.")
    papers = data.get("recommendedPapers") or []
    if not papers:
        return {"formatted": "No recommendations found.", "totalResults": 0, "resultsShared": 0}
    title = f"Recommended papers based on {aid or positive_ids}"
    return {"formatted": _format_s2_paper_list(papers[:limit], title), "totalResults": len(papers), "resultsShared": min(limit, len(papers))}


# ---------------------------------------------------------------------------
# Operation dispatch
# ---------------------------------------------------------------------------

_OPERATIONS = {
    "trending": _op_trending,
    "search": _op_search,
    "paper_details": _op_paper_details,
    "read_paper": _op_read_paper,
    "citation_graph": _op_citation_graph,
    "snippet_search": _op_snippet_search,
    "recommend": _op_recommend,
    "find_datasets": _op_find_datasets,
    "find_models": _op_find_models,
    "find_collections": _op_find_collections,
    "find_all_resources": _op_find_all_resources,
}


class HfPapersTool(BaseTool):
    name = "hf_papers"
    description = (
        "Discover ML research papers, analyze citations, search paper contents, and find linked resources.\n\n"
        "Combines HuggingFace Hub, arXiv, and Semantic Scholar. Use for exploring research areas, "
        "finding datasets for a task, tracing citation chains, or implementing a paper's approach.\n\n"
        "Typical flows:\n"
        "  search → read_paper → find_all_resources → hf_inspect_dataset\n"
        "  search → paper_details → citation_graph → read_paper (trace influence)\n"
        "  snippet_search → paper_details → read_paper (find specific claims)\n\n"
        "Operations:\n"
        "- trending: Get trending daily papers, optionally filter by topic keyword\n"
        "- search: Search papers. Uses HF by default (ML-tuned). Add date_from/min_citations/categories to use Semantic Scholar with filters\n"
        "- paper_details: Metadata, abstract, AI summary, github link\n"
        "- read_paper: Read paper contents — without section: abstract + TOC; with section: full text\n"
        "- citation_graph: Get references and citations for a paper with influence flags and citation intents\n"
        "- snippet_search: Semantic search over full-text passages from 12M+ papers\n"
        "- recommend: Find similar papers (single paper or positive/negative examples)\n"
        "- find_datasets: Find datasets linked to a paper\n"
        "- find_models: Find models linked to a paper\n"
        "- find_collections: Find collections that include a paper\n"
        "- find_all_resources: Parallel fetch of datasets + models + collections for a paper"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": list(_OPERATIONS.keys()),
                "description": "Operation to execute.",
            },
            "query": {
                "type": "string",
                "description": "Search query. Required for: search, snippet_search. Optional for: trending (filters by keyword).",
            },
            "arxiv_id": {
                "type": "string",
                "description": "ArXiv paper ID (e.g. '2305.18290'). Required for: paper_details, read_paper, citation_graph, find_datasets, find_models, find_collections, find_all_resources. Optional for: recommend.",
            },
            "section": {
                "type": "string",
                "description": "Section name or number to read (e.g. '3', 'Experiments', '4.2'). Optional for: read_paper.",
            },
            "direction": {
                "type": "string",
                "enum": ["citations", "references", "both"],
                "description": "Direction for citation_graph. Default: both.",
            },
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format. Optional for: trending.",
            },
            "date_from": {
                "type": "string",
                "description": "Start date (YYYY-MM-DD). Triggers Semantic Scholar search. For: search, snippet_search.",
            },
            "date_to": {
                "type": "string",
                "description": "End date (YYYY-MM-DD). Triggers Semantic Scholar search. For: search, snippet_search.",
            },
            "categories": {
                "type": "string",
                "description": "Field of study filter (e.g. 'Computer Science'). Triggers Semantic Scholar search.",
            },
            "min_citations": {
                "type": "integer",
                "description": "Minimum citation count filter. Triggers Semantic Scholar search.",
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "citationCount", "publicationDate"],
                "description": "Sort order for Semantic Scholar search. Default: relevance.",
            },
            "positive_ids": {
                "type": "string",
                "description": "Comma-separated arxiv IDs for multi-paper recommendations. For: recommend.",
            },
            "negative_ids": {
                "type": "string",
                "description": "Comma-separated arxiv IDs as negative examples. For: recommend.",
            },
            "sort": {
                "type": "string",
                "enum": ["downloads", "likes", "trending"],
                "description": "Sort order for find_datasets and find_models. Default: downloads.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default: 10, max: 50).",
            },
        },
        "required": ["operation"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Extract all parameters from the raw input
        args: dict[str, Any] = {}
        for key in ("operation", "query", "arxiv_id", "section", "direction", "date",
                     "date_from", "date_to", "categories", "min_citations", "sort_by",
                     "positive_ids", "negative_ids", "sort", "limit"):
            val = getattr(input_data, key, None)
            if val is not None:
                args[key] = val
        # Also check extra fields
        if hasattr(input_data, "extra") and isinstance(input_data.extra, dict):
            args.update(cast(dict[str, Any], input_data.extra))

        operation = args.get("operation")
        if not operation:
            return ToolOutput(success=False, result=None, error="'operation' parameter is required.")

        handler = _OPERATIONS.get(operation)
        if not handler:
            return ToolOutput(success=False, result=None, error=f"Unknown operation: '{operation}'. Valid: {', '.join(_OPERATIONS.keys())}")

        limit = min(args.get("limit", DEFAULT_LIMIT), MAX_LIMIT)
        try:
            result = await handler(args, limit)
            return ToolOutput(success=not result.get("isError", False), result=result["formatted"])
        except httpx.HTTPStatusError as e:
            return ToolOutput(success=False, result=None, error=f"API error: {e.response.status_code}")
        except httpx.RequestError as e:
            return ToolOutput(success=False, result=None, error=f"Request error: {e}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error in {operation}: {e}")
