"""Real-time information lookup using Gemini Flash.

Provides a tool for Gemma to look up current, live information
from the web using Google Search grounding.
"""

import logging
import os
from google import genai
from google.genai import types as genai_types

from .registry import registry

logger = logging.getLogger(__name__)


@registry.register
def get_realtime_info(query: str) -> str:
    """Search the web for current, real-time information (news, weather, live data).
    Use this whenever the user asks for information that changes frequently.
    
    query: The search query to look up (e.g., 'weather in London today', 'latest tech news')
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Real-time search is unavailable because the Gemini API key is not configured."

    try:
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Use Gemini with Google Search grounding to answer the query
        system_instruction = (
            "You are a real-time data retrieval tool. Your job is to answer the query "
            "using your search capabilities. Keep your answer concise, accurate, and direct. "
            "Do not include conversational filler. Just return the facts."
        )

        response = client.models.generate_content(
            model=model,
            contents=query,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            ),
        )

        if response.text:
            return response.text
        return "No relevant real-time information found."

    except Exception as e:
        logger.error(f"Real-time lookup failed: {e}")
        return f"Failed to retrieve real-time data: {type(e).__name__}"
