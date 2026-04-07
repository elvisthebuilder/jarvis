"""Clipboard operations — read and write system clipboard.

Uses wl-copy/wl-paste for Wayland, with xclip fallback for X11.
"""

import subprocess
import logging

from .registry import registry

logger = logging.getLogger(__name__)


def _is_wayland() -> bool:
    """Check if we're running on Wayland."""
    import os
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


@registry.register
def get_clipboard() -> str:
    """Get the current contents of the system clipboard."""
    if _is_wayland():
        result = subprocess.run(
            ["wl-paste", "--no-newline"],
            capture_output=True, text=True, timeout=5,
        )
    else:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=5,
        )

    if result.returncode == 0:
        content = result.stdout
        if not content:
            return "Clipboard is empty."
        # Truncate very long content
        if len(content) > 500:
            return f"Clipboard contents (truncated): {content[:500]}..."
        return f"Clipboard contents: {content}"
    return "Failed to read clipboard."


@registry.register
def set_clipboard(text: str) -> str:
    """Copy text to the system clipboard.
    
    text: The text to copy to clipboard
    """
    if _is_wayland():
        result = subprocess.run(
            ["wl-copy", text],
            capture_output=True, text=True, timeout=5,
        )
    else:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text, capture_output=True, text=True, timeout=5,
        )

    if result.returncode == 0:
        preview = text[:80] + "..." if len(text) > 80 else text
        return f"Copied to clipboard: {preview}"
    return "Failed to write to clipboard."
