"""Scrape tool — fetch/scrape web page content."""

from typing import Any

from core.windows.analytics import with_analytics


def create_scrape_tool(desktop, analytics=None):
    """Create a scrape tool."""
    @with_analytics(analytics, "Scrape-Tool")
    async def scrape_tool(
        url: str,
        query: str | None = None,
        use_dom: bool | str = False,
        use_sampling: bool | str = True,
    ) -> str:
        use_dom = use_dom is True or (isinstance(use_dom, str) and use_dom.lower() == "true")
        use_sampling = use_sampling is True or (isinstance(use_sampling, str) and use_sampling.lower() == "true")

        if not use_dom:
            content = desktop.scrape(url)
        else:
            desktop_state = desktop.get_state(use_vision=False, use_dom=True)
            tree_state = desktop_state.tree_state
            if not tree_state.dom_node:
                return f"No DOM information found. Please open {url} in browser first."
            dom_node = tree_state.dom_node
            vertical_scroll_percent = getattr(dom_node, 'vertical_scroll_percent', 0)
            content = "\n".join([node.text for node in tree_state.dom_informative_nodes])
            header_status = "Reached top" if vertical_scroll_percent <= 0 else "Scroll up to see more"
            footer_status = (
                "Reached bottom" if vertical_scroll_percent >= 100 else "Scroll down to see more"
            )
            content = f"{header_status}\n{content}\n{footer_status}"

        return f"URL: {url}\nContent:\n{content}"
    
    return scrape_tool