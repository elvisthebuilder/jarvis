"""Preference learning and management.

Extracts and manages user preferences from explicit statements
and implicit behavioral patterns.
"""

import logging
from .store import MemoryStore

logger = logging.getLogger(__name__)

# Keywords that signal explicit preferences
PREFERENCE_SIGNALS = {
    "prefer": True,
    "like": True,
    "love": True,
    "enjoy": True,
    "favorite": True,
    "favourite": True,
    "always use": True,
    "don't like": False,
    "hate": False,
    "dislike": False,
    "never": False,
    "stop": False,
}


class PreferenceManager:
    """Manages user preferences — both explicit and inferred.
    
    Explicit: User says "I prefer dark mode" → stored directly
    Inferred: User always plays lofi when coding → stored with lower confidence
    """

    def __init__(self, store: MemoryStore):
        self.store = store
        self._cache: dict[str, str] = {}

    async def load_preferences(self):
        """Load all preferences into cache."""
        self._cache = await self.store.get_all_preferences()
        logger.info(f"Loaded {len(self._cache)} preferences")

    async def extract_and_store(self, user_input: str) -> list[str]:
        """Attempt to extract preferences from user input.
        
        Returns:
            List of preference keys that were updated
        """
        updated = []
        input_lower = user_input.lower()

        for signal, positive in PREFERENCE_SIGNALS.items():
            if signal in input_lower:
                # Simple extraction: store the full statement as a preference
                key = f"stated_{'likes' if positive else 'dislikes'}_{len(self._cache)}"
                await self.store.set_preference(
                    key=key,
                    value=user_input,
                    source="explicit",
                    confidence=1.0,
                )
                self._cache[key] = user_input
                updated.append(key)
                break

        return updated

    async def record_tool_usage(self, tool_name: str, context: str = ""):
        """Record that a tool was used — for inferring implicit preferences.
        
        Over time, patterns like "always uses dark mode at night" emerge.
        """
        await self.store.record_pattern(
            pattern_type="tool_usage",
            description=f"Used {tool_name}",
            data=context,
        )

    def get_preferences_for_prompt(self) -> dict[str, str]:
        """Get preferences formatted for system prompt injection."""
        return dict(self._cache)

    async def set_explicit(self, key: str, value: str):
        """Set an explicit user preference."""
        await self.store.set_preference(key, value, source="explicit", confidence=1.0)
        self._cache[key] = value

    async def get(self, key: str) -> str | None:
        """Get a preference value."""
        return self._cache.get(key) or await self.store.get_preference(key)
