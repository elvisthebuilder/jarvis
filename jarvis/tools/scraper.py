import asyncio
import httpx
from bs4 import BeautifulSoup
import logging
from typing import Optional

from .registry import registry

logger = logging.getLogger(__name__)

@registry.register
async def scrape_website_content(url: str) -> str:
    """Read the text content of a website to gather deep intelligence.
    
    Use this when you need to research the details of a tool, framework, or company
    after finding their URL via a search.
    
    url: The website address to read (e.g., 'https://github.com/project')
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove noise
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
            
            # Get text and clean up whitespace
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            # Truncate to avoid context window explosion (keeping ~2000 words)
            limit = 8000
            if len(text) > limit:
                return text[:limit] + "\n\n[Content truncated for brevity, Sir...]"
            
            return text if text else "I was unable to extract any readable text from this page, Sir."

    except Exception as e:
        logger.error(f"Scraping failed for {url}: {e}")
        return f"Failed to retrieve content from {url}: {type(e).__name__}"
