"""Web fetch and search tools for extracting information from URLs"""


import json
import httpx
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


class WebFetchTool(BaseTool):
    """Tool for fetching and processing content from URLs"""

    name = "fetch_webpage"
    description = """Fetches the main content from a web page. This tool is useful for summarizing or analyzing the content of a webpage. Use this tool when you think the user is looking for information from a specific webpage.

Usage:
- Provide an array of URLs to fetch content from
- Use the query parameter to describe what information you're looking for in the page content
- Content is truncated at 2000 characters to manage response size
- Use this for research, documentation retrieval, and information gathering
- Note: This tool uses basic HTTP fetching and may not work well with JavaScript-rendered pages
- For complex web scraping, consider using specialized tools or APIs"""
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
        # Support both camelCase and snake_case parameter names
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
    """Tool for searching the web using Exa MCP API"""

    name = "web_search"
    description = """Searches the web using Exa's MCP API for real-time information. Use this tool when you need to find current information, news, or research topics on the internet.

Usage:
- Provide a search query as a string
- Optionally specify the number of results (default: 8)
- Optionally set search type: 'auto', 'neural', or 'keyword' (default: 'auto')
- Optionally enable livecrawling for fresh content: 'fallback', 'always', or 'never' (default: 'fallback')
- Returns structured search results with titles, URLs, and content snippets
- Ideal for researching recent events, technical documentation, or current topics
- More reliable than basic web fetching for finding specific information"""
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find information on the web"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of search results to return (default: 8)",
                "default": 8,
                "minimum": 1,
                "maximum": 20
            },
            "numResults": {
                "type": "integer",
                "description": "Number of search results to return (default: 8) - camelCase variant",
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
            "context_max_characters": {
                "type": "integer",
                "description": "Maximum characters for content context (optional)"
            },
            "contextMaxCharacters": {
                "type": "integer",
                "description": "Maximum characters for content context (optional) - camelCase variant"
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
        # Support both camelCase and snake_case parameter names
        query = self._get_param(input_data, "query")
        num_results = self._get_param(input_data, "num_results", "numResults") or 8
        search_type = self._get_param(input_data, "type") or "auto"
        livecrawl = self._get_param(input_data, "livecrawl") or "fallback"
        context_max_characters = self._get_param(input_data, "context_max_characters")

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
            "numResults": num_results,
            "livecrawl": livecrawl,
        }
        if context_max_characters is not None:
            payload_args["contextMaxCharacters"] = context_max_characters

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
                            "num_results": num_results,
                            "search_type": search_type
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
                            "num_results": num_results,
                            "search_type": search_type
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
