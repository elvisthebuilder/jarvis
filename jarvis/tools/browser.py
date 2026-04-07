import subprocess
import urllib.parse
import logging
import json
from pathlib import Path

import requests

from .registry import registry

logger = logging.getLogger(__name__)

DEBUG_URL = "http://localhost:9222/json"


def _get_tabs() -> list[dict]:
    """Internal helper to get all open tabs from the debugging port."""
    try:
        response = requests.get(DEBUG_URL, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.debug(f"Failed to connect to browser debugging port: {e}")
    return []


@registry.register
def open_url(url: str, enable_debugging: bool = False) -> str:
    """Open a URL in the web browser.
    
    url: The full URL to open (e.g., 'https://github.com')
    enable_debugging: If True, restarts/starts browser with remote debugging enabled (needed for specific tab control).
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if enable_debugging:
        launcher = Path(__file__).parents[2] / "scripts" / "browser_launcher.sh"
        # Try to find which browser is currently running or default to brave
        browser_type = "brave"
        subprocess.Popen([str(launcher), browser_type, url])
        return f"Launching {browser_type} with remote debugging enabled for {url}."

    result = subprocess.run(
        ["xdg-open", url],
        capture_output=True, text=True, timeout=30,
    )
    
    if result.returncode == 0:
        return f"Opened {url} in your browser."
    return f"Failed to open URL: {result.stderr.strip()}"


@registry.register
def search_web(query: str) -> str:
    """Open a web search in the default browser.
    
    query: What to search for on the web
    """
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    return open_url(url)


@registry.register
def list_tabs() -> str:
    """Get a list of all open browser tabs (titles and URLs).
    
    Note: Requires the browser to be launched with --remote-debugging-port=9222.
    """
    tabs = _get_tabs()
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    
    if not page_tabs:
        return (
            "I couldn't find any open tabs with remote debugging enabled. "
            "Please ensure your browser is launched with --remote-debugging-port=9222. "
            "You can ask me to 'open browser with debugging' to set this up, Sir."
        )

    res = ["Open Tabs:"]
    for i, t in enumerate(page_tabs, 1):
        title = t.get("title", "Untitled")
        url = t.get("url", "unknown")
        res.append(f"{i}. {title} ({url})")
    
    return "\n".join(res)


@registry.register
def close_tab(tab_id: str) -> str:
    """Close a specific browser tab by its unique internal ID.
    
    tab_id: The ID obtained from list_tabs()
    """
    try:
        response = requests.get(f"{DEBUG_URL}/close/{tab_id}", timeout=2)
        if response.status_code == 200:
            return "Tab closed successfully."
        return f"Failed to close tab. Browser returned status: {response.status_code}"
    except Exception as e:
        return f"Error connecting to browser: {e}"


@registry.register
def find_and_close_tab(query: str) -> str:
    """Search for a tab by title or URL and close it if found.
    
    query: Part of the tab title or URL to match
    """
    tabs = _get_tabs()
    query = query.lower()
    
    match = None
    for t in tabs:
        if t.get("type") != "page":
            continue
        if query in t.get("title", "").lower() or query in t.get("url", "").lower():
            match = t
            break
    
    if match:
        return close_tab(match["id"])
    
    return f"I couldn't find any tab matching '{query}', Sir."
