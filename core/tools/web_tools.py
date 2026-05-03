"""Web fetch and search tools for extracting information from URLs"""


import json
import httpx
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


class WebFetchTool(BaseTool):
    """Tool for fetching and processing content from URLs"""

    name = "fetch_webpage"
    description = """Fetch and extract content from web pages.

WHEN TO USE:
- Getting documentation from URLs
- Fetching API responses
- Reading articles or blog posts

Parameters:
- urls (REQUIRED): Array of URLs to fetch content from
- query (OPTIONAL): Search query to filter/extract specific information

Returns: Content truncated at 2000 characters.
Limitation: Not suitable for JavaScript-rendered pages (use web_search for dynamic content).
Content is extracted in LLM-friendly format."""
    input_schema = {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "An array of URLs to fetch content from",
                "minItems": 1
            },
            "query": {
                "type": "string",
                "description": "The query to search for in the web page's content. This should be a clear and concise description of the content you want to find."
            }
        },
        "required": ["urls"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support camelCase parameter names
        urls = self._get_param(input_data, "urls")
        query = self._get_param(input_data, "query") or ""

        if not isinstance(urls, list) or not urls or not all(isinstance(url, str) for url in urls):
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid URL list: urls parameter must be a non-empty list of strings. Please provide valid URLs."
            )

        if not isinstance(query, str):
            query = ""

        results = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                for url in urls:
                    try:
                        response = await client.get(url, timeout=30.0)
                        response.raise_for_status()

                        # Return the text content
                        content = response.text

                        results.append({
                            "url": url,
                            "content": content[:2000] + "..." if len(content) > 2000 else content,
                            "status": response.status_code
                        })
                    except Exception as e:
                        results.append({
                            "url": url,
                            "error": str(e),
                            "status": "failed"
                        })

            return ToolOutput(
                success=True,
                result=results,
                metadata={"url_count": len(urls), "query": query}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Web fetch failed: {str(e)}. Please check if the URLs are valid, accessible, and if you have an internet connection."
            )


class ExaWebSearchTool(BaseTool):
    """Tool for searching the web using Exa API"""

    name = "web_search"
    description = """Search the web using Exa API for current information.

WHEN TO USE:
- Researching latest information
- Finding documentation or tutorials
- Getting up-to-date news or releases

Parameters:
- query (REQUIRED): Search query string
- numResults (OPTIONAL): Number of results (default: 8, max: 20)
- type (OPTIONAL): 'auto' (default), 'neural', or 'keyword'
- livecrawl (OPTIONAL): 'fallback' (default), 'always', or 'never'
- contextMaxCharacters (OPTIONAL): Max characters for content

Returns: Search results with titles, URLs, and content snippets."""
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find information on the web"
            },
            "numResults": {
                "type": "integer",
                "description": "Number of search results to return (default: 8)",
                "default": 8,
                "minimum": 1,
                "maximum": 20
            },
            "type": {
                "type": "string",
                "description": "Search type: 'auto', 'neural', or 'keyword' (default: 'auto')",
                "enum": ["auto", "neural", "keyword"],
                "default": "auto"
            },
            "livecrawl": {
                "type": "string",
                "description": "Livecrawl mode: 'fallback', 'always', or 'never' (default: 'fallback')",
                "enum": ["fallback", "always", "never"],
                "default": "fallback"
            },
            "contextMaxCharacters": {
                "type": "integer",
                "description": "Maximum characters for content context (optional)"
            }
        },
        "required": ["query"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    def __init__(self):
        super().__init__()
        self.mcp_url = "https://mcp.exa.ai/mcp"
        self.timeout = 25

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support camelCase parameter names
        query = self._get_param(input_data, "query")
        numResults = self._get_param(input_data, "numResults") or 8
        search_type = self._get_param(input_data, "type") or "auto"
        livecrawl = self._get_param(input_data, "livecrawl") or "fallback"
        contextMaxCharacters = self._get_param(input_data, "contextMaxCharacters")

        if not isinstance(query, str) or not query.strip():
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid query: must be a non-empty string"
            )

        # Build payload
        payload_args = {
            "query": query,
            "type": search_type,
            "numResults": numResults,
            "livecrawl": livecrawl,
        }
        if contextMaxCharacters is not None:
            payload_args["contextMaxCharacters"] = contextMaxCharacters

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "web_search_exa",
                "arguments": payload_args,
            },
        }

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.mcp_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

            # Parse SSE response
            body = response.text
            for line in body.splitlines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[len("data: "):])
                except json.JSONDecodeError:
                    continue

                result = data.get("result", {})
                content = result.get("content", [])
                if content and isinstance(content, list) and content[0].get("text"):
                    return ToolOutput(
                        success=True,
                        result=content[0]["text"],
                        metadata={
                            "query": query,
                            "numResults": numResults,
                            "searchType": search_type
                        }
                    )

            # Fallback: try parsing whole body as JSON
            try:
                j = response.json()
                result = j.get("result", {})
                content = result.get("content", [])
                if content and isinstance(content, list) and content[0].get("text"):
                    return ToolOutput(
                        success=True,
                        result=content[0]["text"],
                        metadata={
                            "query": query,
                            "numResults": numResults,
                            "searchType": search_type
                        }
                    )
            except Exception:
                pass

            return ToolOutput(
                success=False,
                result=None,
                error="No search result text extracted from Exa API response"
            )

        except httpx.TimeoutException:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Request to Exa API timed out after {self.timeout} seconds"
            )
        except httpx.HTTPStatusError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Exa API returned error {e.response.status_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Web search failed: {str(e)}"
            )
