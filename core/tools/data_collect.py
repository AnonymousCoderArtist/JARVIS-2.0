"""Data Collect Tool - Fetch data from configured connectors

This tool allows agents to fetch data from external services through connectors.
Similar to OpenJarvis's digest_collect tool.

Usage:
    - Use this tool to fetch data from email, calendar, weather, news, etc.
    - Specify the sources (connector IDs) you want to fetch from
    - Data is returned in a structured, human-readable format
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import logging

from core.tools.base import BaseTool, ToolInput, ToolOutput
from core.tools.registry import ToolRegistry
from core.connectors import ConnectorRegistry, Document

logger = logging.getLogger(__name__)


# Default sources to query
DEFAULT_SOURCES = ["rss", "weather", "github", "http"]


class DataCollectInput(ToolInput):
    """Input for the data_collect tool"""
    sources: List[str] | None = None  # List of connector IDs (e.g., ["weather", "github"])
    hours_back: int = 24  # How many hours back to look
    max_per_source: int = 15  # Maximum items per source
    query: str | None = None  # Optional query (for future use)


class DataCollectTool(BaseTool):
    """Tool to collect data from configured connectors"""
    
    name = "data_collect"
    description = (
        "Fetch recent data from configured connectors (weather, GitHub, RSS feeds, "
        "HTTP endpoints, etc.) and return a structured, human-readable summary. "
        "Use this to get current information from external services."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of connector IDs to fetch from. "
                    "Available: weather, github, rss, http, filesystem. "
                    "Leave empty to use default sources."
                ),
            },
            "hours_back": {
                "type": "number",
                "description": "How many hours back to look (default: 24)",
            },
            "max_per_source": {
                "type": "number",
                "description": "Maximum items per source (default: 15)",
            },
            "query": {
                "type": "string",
                "description": "Optional query for filtering (not implemented yet)",
            },
        },
    }
    is_deferred = False
    search_hint = "fetch data from external services like weather github rss news"
    
    def __init__(self, tool_registry: ToolRegistry | None = None, **kwargs):
        super().__init__(tool_registry, **kwargs)
    
    async def execute(self, input: DataCollectInput, context: Any = None) -> ToolOutput:
        """Execute the data collection"""
        
        try:
            # Determine which sources to query
            sources = input.sources or DEFAULT_SOURCES
            hours_back = input.hours_back or 24
            max_per_source = input.max_per_source or 15
            
            # Calculate since timestamp
            since = datetime.now() - timedelta(hours=hours_back)
            
            # Collect data from each connector
            results = []
            errors = []
            
            for source in sources:
                try:
                    # Get connector from registry
                    connector = ConnectorRegistry.get(source)
                    
                    if not connector:
                        errors.append(f"Connector '{source}' not found")
                        continue
                    
                    if not connector.is_connected():
                        errors.append(f"Connector '{source}' not connected (no credentials)")
                        continue
                    
                    # Sync data from connector
                    docs = []
                    for doc in connector.sync(since=since):
                        docs.append(doc)
                        if len(docs) >= max_per_source:
                            break
                    
                    # Format each document
                    if docs:
                        results.append(f"=== {source.upper()} ===")
                        for doc in docs:
                            formatted = self._format_document(doc)
                            results.append(formatted)
                        results.append("")  # Blank line between sections
                    
                except Exception as e:
                    logger.error(f"Error fetching from {source}: {e}")
                    errors.append(f"Error fetching from '{source}': {str(e)}")
            
            # Build final output
            output_parts = []
            
            if results:
                output_parts.extend(results)
            
            if errors:
                output_parts.append("=== ERRORS ===")
                output_parts.extend(errors)
            
            if not results and not errors:
                output_parts.append("No data available. Connectors may need configuration.")
            
            return ToolOutput(
                success=True,
                result="\n".join(output_parts),
                metadata={
                    "sources_queried": sources,
                    "sources_ok": [s for s in sources if ConnectorRegistry.get(s) and ConnectorRegistry.get(s).is_connected()],
                    "errors": errors,
                }
            )
            
        except Exception as e:
            logger.error(f"DataCollectTool error: {e}")
            return ToolOutput(
                success=False,
                result="",
                error=str(e)
            )
    
    def _format_document(self, doc: Document) -> str:
        """Format a Document into a human-readable line"""
        
        if doc.source == "weather":
            return self._format_weather(doc)
        elif doc.source == "github":
            return self._format_github(doc)
        elif doc.source == "rss":
            return self._format_rss(doc)
        elif doc.source == "http":
            return self._format_http(doc)
        else:
            # Generic format
            return f"[{doc.source}] {doc.title}"
    
    def _format_weather(self, doc: Document) -> str:
        """Format weather document"""
        meta = doc.metadata
        if doc.doc_type == "current":
            temp = meta.get("temp", "?")
            conditions = meta.get("conditions", "?")
            return f"[weather] Current: {temp}°F, {conditions}"
        else:
            return f"[weather] Forecast: {doc.title}"
    
    def _format_github(self, doc: Document) -> str:
        """Format GitHub document"""
        meta = doc.metadata
        repo = meta.get("repo", "")
        reason = meta.get("reason", "")
        
        if doc.doc_type == "notification":
            return f"[github] {doc.title} ({reason})"
        elif doc.doc_type == "pull_request":
            draft = "draft" if meta.get("draft") else ""
            return f"[github] PR: {doc.title} in {repo} {draft}"
        else:
            return f"[github] {doc.title} in {repo}"
    
    def _format_rss(self, doc: Document) -> str:
        """Format RSS document"""
        feed = doc.metadata.get("feed_title", "news")
        return f"[{feed}] {doc.title}"
    
    def _format_http(self, doc: Document) -> str:
        """Format HTTP document"""
        status = doc.metadata.get("status_code", "")
        return f"[http] {doc.title} (status: {status})"


# Register the tool
def register_data_collect_tool(registry: ToolRegistry):
    """Register the data_collect tool with the registry"""
    tool = DataCollectTool(tool_registry=registry)
    registry.register(tool)
    logger.info("Registered data_collect tool")


# For direct execution
async def run_data_collect(
    sources: List[str] | None = None,
    hours_back: int = 24,
    max_per_source: int = 15
) -> str:
    """Run data collection directly (for testing)"""
    tool = DataCollectTool()
    input_obj = DataCollectInput(
        sources=sources,
        hours_back=hours_back,
        max_per_source=max_per_source
    )
    result = await tool.execute(input_obj)
    return result.result


__all__ = ["DataCollectTool", "DataCollectInput", "register_data_collect_tool", "run_data_collect"]