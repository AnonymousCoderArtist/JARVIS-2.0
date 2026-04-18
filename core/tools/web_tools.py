"""Web fetch tool for extracting information from URLs"""


import httpx

from .base import BaseTool, ToolInput, ToolOutput


class WebFetchTool(BaseTool):
    """Tool for fetching and processing content from URLs (Copilot Chat style)"""

    name = "fetch_webpage"
    description = "Fetches the main content from a web page. This tool is useful for summarizing or analyzing the content of a webpage. You should use this tool when you think the user is looking for information from a specific webpage."
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
        "required": ["urls", "query"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        urls = getattr(input_data, "urls", None)
        query = getattr(input_data, "query", None)

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
                error=f"Web fetch failed: {str(e)}"
            )
