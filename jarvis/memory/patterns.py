"""Pattern detection engine for Jarvis.

Analyzes interaction history to detect recurring usage patterns
and generate proactive suggestions.
"""

import logging
from datetime import datetime
from collections import Counter

from .store import MemoryStore

logger = logging.getLogger(__name__)


class PatternEngine:
    """Detects usage patterns from interaction history.
    
    Analyzes when and how the user interacts with Jarvis to:
    - Detect time-based routines (e.g., music at 8 AM daily)
    - Identify tool usage patterns (e.g., always enables dark mode at night)
    - Generate proactive suggestions
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    async def analyze(self) -> list[dict]:
        """Run pattern analysis on recent interactions.
        
        Returns:
            List of detected pattern dicts with type, description, and confidence.
        """
        patterns = []

        # Get recent interactions
        interactions = await self.store.get_recent_interactions(limit=100)
        if len(interactions) < 5:
            return patterns  # Not enough data yet

        # Analyze tool usage frequency
        tool_patterns = self._analyze_tool_frequency(interactions)
        patterns.extend(tool_patterns)

        # Analyze time-based patterns
        time_patterns = self._analyze_time_patterns(interactions)
        patterns.extend(time_patterns)

        # Store detected patterns
        for pattern in patterns:
            await self.store.record_pattern(
                pattern_type=pattern["type"],
                description=pattern["description"],
                data=str(pattern.get("data", "")),
            )

        return patterns

    def _analyze_tool_frequency(self, interactions: list[dict]) -> list[dict]:
        """Find frequently used tools."""
        patterns = []
        tool_counts = Counter()

        for interaction in interactions:
            tools = interaction.get("tools_used", "")
            if tools:
                for tool in tools.split(","):
                    tool_counts[tool.strip()] += 1

        for tool, count in tool_counts.most_common(5):
            if count >= 3:
                patterns.append({
                    "type": "frequent_tool",
                    "description": f"Frequently uses {tool} ({count} times recently)",
                    "data": {"tool": tool, "count": count},
                    "confidence": min(count / 10, 1.0),
                })

        return patterns

    def _analyze_time_patterns(self, interactions: list[dict]) -> list[dict]:
        """Find time-based usage patterns."""
        patterns = []
        hour_counts = Counter()

        for interaction in interactions:
            ts = interaction.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    hour_counts[dt.hour] += 1
                except (ValueError, TypeError):
                    continue

        # Find peak usage hours
        for hour, count in hour_counts.most_common(3):
            if count >= 3:
                period = "morning" if 5 <= hour < 12 else \
                         "afternoon" if 12 <= hour < 17 else \
                         "evening" if 17 <= hour < 21 else "late night"
                patterns.append({
                    "type": "time_pattern",
                    "description": f"Most active during {period} (around {hour}:00)",
                    "data": {"hour": hour, "count": count},
                    "confidence": min(count / 10, 1.0),
                })

        return patterns

    async def get_suggestions(self) -> list[str]:
        """Generate proactive suggestions based on detected patterns.
        
        Returns:
            List of suggestion strings Jarvis can present to the user.
        """
        suggestions = []
        patterns = await self.store.get_frequent_patterns(min_frequency=5)

        for pattern in patterns:
            ptype = pattern.get("pattern_type", "")
            desc = pattern.get("description", "")
            
            if ptype == "frequent_tool" and "play_spotify" in desc:
                suggestions.append(
                    "You seem to enjoy music. Shall I set up a routine playlist?"
                )
            elif ptype == "time_pattern" and "evening" in desc:
                suggestions.append(
                    "You're often active in the evenings. Want me to auto-enable "
                    "night light and dark mode around that time?"
                )

        return suggestions[:3]  # Max 3 suggestions at a time
