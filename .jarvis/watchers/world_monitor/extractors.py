"""WorldMonitor Content Extractors for all subsets"""

import feedparser
import re
from typing import Any

class ContentExtractors:
    @staticmethod
    def _strip_html(text: str) -> str:
        """Removes HTML tags from a string."""
        return re.sub(r'<[^>]+>', '', text)

    @staticmethod
    def rss(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Handles RSS feeds using feedparser and strips HTML."""
        items = []
        feed = feedparser.parse(data.get("rss_content", ""))
        for entry in feed.entries[:5]:
            title = ContentExtractors._strip_html(entry.get('title', ''))
            summary = ContentExtractors._strip_html(entry.get('summary', ''))
            items.append({
                "source": entry.get("author", "RSS"),
                "text": f"{title}: {summary}"
            })
        return items

    @staticmethod
    def telegram(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "items" in data:
            for item in data["items"]:
                text = item.get("text", "")[:300]
                channel = item.get("channelTitle", item.get("channel", "Unknown"))
                if text:
                    items.append({"source": channel, "text": text})
        return items

    @staticmethod
    def feed(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "items" in data:
            for item in data["items"]:
                text = item.get("title", item.get("headline", ""))[:300]
                source = item.get("source", item.get("publisher", "Unknown"))
                if text:
                    items.append({"source": source, "text": text})
        return items

    @staticmethod
    def pizzint(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "pizzint" in data:
            p = data["pizzint"]
            items.append({
                "source": "PIZZINT",
                "text": f"DEFCON {p.get('defconLevel', '?')}: {p.get('defconLabel', '')} - Activity: {p.get('aggregateActivity', 0)}",
                "urgent": int(p.get('defconLevel', 5)) <= 3
            })
        return items

    @staticmethod
    def military(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "items" in data:
            for item in data["items"]:
                text = item.get("text", item.get("title", ""))[:300]
                if text:
                    items.append({"source": "MILITARY", "text": text})
        return items

    @staticmethod
    def oref(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "alerts" in data:
            for alert in data["alerts"]:
                text = alert.get("title", alert.get("description", ""))[:300]
                if text:
                    items.append({"source": "OREF", "text": text, "urgent": True})
        return items

    @staticmethod
    def supply_chain(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for k in ["disruptions", "items"]:
            if k in data:
                for d in data[k]:
                    text = d.get("title", d.get("description", ""))[:300]
                    source = d.get("country", d.get("source", "Supply Chain"))
                    if text:
                        items.append({"source": source, "text": text})
        return items

    @staticmethod
    def climate(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for k in ["fires", "alerts", "items"]:
            if k in data:
                for item in data[k]:
                    text = item.get("title", item.get("description", f"Fire at {item.get('location')}"))[:300]
                    if text:
                        items.append({"source": "CLIMATE", "text": text})
        return items

    @staticmethod
    def markets(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        if "index" in data and "value" in data: # Fear & Greed
            items.append({"source": "MARKETS", "text": f"Fear & Greed Index: {data['value']} ({data.get('value_text', '')})"})
        elif "items" in data:
            for item in data["items"]:
                text = item.get("text", item.get("title", ""))[:300]
                if text:
                    items.append({"source": "MARKETS", "text": text})
        return items

    @staticmethod
    def generic(endpoint: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        # Try to find a list of items
        for key in ["items", "events", "signals", "data", "results"]:
            if key in data and isinstance(data[key], list):
                for item in data[key][:5]:
                    if isinstance(item, dict):
                        text = item.get("text", item.get("title", item.get("description", "")))[:300]
                        source = item.get("source", item.get("country", endpoint.upper()))
                        if text:
                            items.append({"source": source, "text": text})
                break
        return items

    @classmethod
    def extract(cls, endpoint: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        # RSS check - prioritize if rss_content exists
        if "rss_content" in data:
            return cls.rss(data)
            
        extractors = {
            "telegram": cls.telegram,
            "feed": cls.feed,
            "pizzint": cls.pizzint,
            "military": cls.military,
            "oref": cls.oref,
            "energy": cls.supply_chain,
            "pipelines": cls.supply_chain,
            "chokepoints": cls.supply_chain,
            "fires": cls.climate,
            "fear": cls.markets,
            "stablecoin": cls.markets,
        }
        extractor = extractors.get(endpoint)
        if extractor:
            return extractor(data)
        return cls.generic(endpoint, data)
