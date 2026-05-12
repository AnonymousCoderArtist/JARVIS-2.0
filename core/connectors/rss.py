"""RSS/News connector - fetches news from RSS feeds"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Try to use feedparser if available, otherwise simple XML parsing
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

from ..base import BaseConnector, ConnectorConfig, Document, SyncStatus
from ..registry import ConnectorRegistry


DEFAULT_CONFIG_DIR = Path.home() / ".jarvis" / "credentials"


# Default RSS feeds to monitor
DEFAULT_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
]


@ConnectorRegistry.register("rss")
class RSSConnector(BaseConnector):
    """Fetch news from RSS feeds"""
    
    connector_id = "rss"
    display_name = "RSS Feeds"
    auth_type = "none"  # Public feeds, no auth needed
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        super().__init__(config)
        self._feeds = DEFAULT_FEEDS.copy()
        self._status = SyncStatus()
        self._load_config()
    
    def _load_config(self):
        """Load configured feeds"""
        # Load from config
        feeds_config = self.config.get_credential("feeds", "")
        if feeds_config:
            if isinstance(feeds_config, list):
                self._feeds = feeds_config
            else:
                self._feeds = [f.strip() for f in feeds_config.split(",") if f.strip()]
    
    def is_connected(self) -> bool:
        """RSS feeds are always "connected" (public)"""
        return True
    
    def disconnect(self) -> None:
        """Nothing to disconnect for RSS"""
        pass
    
    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        """Fetch items from all configured RSS feeds"""
        
        for feed_url in self._feeds:
            try:
                if HAS_FEEDPARSER:
                    parsed = feedparser.parse(feed_url)
                elif HAS_HTTPX:
                    parsed = self._parse_rss_simple(feed_url)
                else:
                    logger.warning("Neither feedparser nor httpx available")
                    continue
                
                feed_title = parsed.get("feed", {}).get("title", feed_url) if isinstance(parsed, dict) else feed_url
                
                # Handle feedparser response
                if HAS_FEEDPARSER and hasattr(parsed, 'entries'):
                    entries = parsed.entries
                elif isinstance(parsed, dict):
                    entries = parsed.get("entries", [])
                else:
                    entries = []
                
                for entry in entries[:10]:  # Limit to 10 per feed
                    # Parse date
                    if hasattr(entry, 'published'):
                        try:
                            timestamp = datetime(*entry.published_parsed[:6])
                        except:
                            timestamp = datetime.now()
                    elif hasattr(entry, 'updated'):
                        try:
                            timestamp = datetime(*entry.updated_parsed[:6])
                        except:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()
                    
                    # Skip old entries
                    if since and timestamp < since:
                        continue
                    
                    # Extract content
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'content'):
                        content = entry.content[0].value if entry.content else ""
                    else:
                        content = ""
                    
                    # Get URL
                    link = ""
                    if hasattr(entry, 'link'):
                        link = entry.link
                    elif isinstance(entry, dict):
                        link = entry.get("link", "")
                    
                    yield Document(
                        doc_id=f"rss-{hash(link)}",
                        source="rss",
                        doc_type="news",
                        content=content[:500],  # Limit content length
                        title=entry.get("title", "No title") if isinstance(entry, dict) else (getattr(entry, 'title', 'No title')),
                        author=entry.get("author", "") if isinstance(entry, dict) else (getattr(entry, 'author', "")),
                        timestamp=timestamp,
                        url=link,
                        metadata={
                            "feed_url": feed_url,
                            "feed_title": feed_title,
                        }
                    )
                    
            except Exception as e:
                logger.debug(f"Failed to fetch feed {feed_url}: {e}")
                continue
        
        self._status.state = "idle"
        self._status.last_sync = datetime.now()
    
    def _parse_rss_simple(self, feed_url: str) -> Dict[str, Any]:
        """Simple RSS parsing without feedparser (fallback)"""
        if not HAS_HTTPX:
            return {"entries": []}
        
        resp = httpx.get(feed_url, timeout=10.0)
        resp.raise_for_status()
        
        # Simple XML parsing - just get titles and links
        content = resp.text
        entries = []
        
        import re
        # Match <item> or <entry> blocks
        items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
        for item in items[:10]:
            title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
            link_match = re.search(r'<link>(.*?)</link>', item)
            desc_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
            
            entries.append({
                "title": title_match.group(1) if title_match else "No title",
                "link": link_match.group(1) if link_match else "",
                "summary": desc_match.group(1) if desc_match else "",
            })
        
        return {"entries": entries, "feed": {"title": feed_url}}
    
    def sync_status(self) -> SyncStatus:
        return self._status
    
    # --- Legacy methods ---
    
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        docs = list(self.sync())
        return [doc.to_dict() for doc in docs[:limit]]
    
    def supports_query_type(self, query_type: str) -> bool:
        return query_type in ["rss", "news", "feed"]
    
    def get_capabilities(self) -> list[str]:
        return ["rss_feeds", "news"]
    
    # --- Configuration ---
    
    def add_feed(self, feed_url: str) -> None:
        """Add an RSS feed to monitor"""
        if feed_url not in self._feeds:
            self._feeds.append(feed_url)
    
    def remove_feed(self, feed_url: str) -> None:
        """Remove an RSS feed"""
        if feed_url in self._feeds:
            self._feeds.remove(feed_url)
    
    def set_feeds(self, feeds: List[str]) -> None:
        """Set all feeds to monitor"""
        self._feeds = feeds


# For backward compatibility
RSSConnectorV2 = RSSConnector