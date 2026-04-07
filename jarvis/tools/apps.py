"""Application launcher and management.

Parses .desktop files to find installed applications and launches them
using gio for Wayland compatibility.
"""

import subprocess
import logging
from pathlib import Path
from functools import lru_cache

from .registry import registry

logger = logging.getLogger(__name__)

# Directories containing .desktop files
DESKTOP_DIRS = [
    Path("/usr/share/applications"),
    Path("/var/lib/snapd/desktop/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local/share/applications",
    Path.home() / ".local/share/flatpak/exports/share/applications",
]


@lru_cache(maxsize=1)
def _get_app_map() -> dict[str, Path]:
    """Build a map of application names to their .desktop file paths.
    
    Returns:
        Dict mapping lowercase app name → .desktop file path
    """
    app_map: dict[str, Path] = {}

    for directory in DESKTOP_DIRS:
        if not directory.exists():
            continue
        for desktop_file in directory.glob("*.desktop"):
            try:
                name = _parse_desktop_name(desktop_file)
                if name:
                    # Store with lowercase key for fuzzy matching
                    app_map[name.lower()] = desktop_file
                    # Also store filename-based key (e.g., "spotify" from "spotify_spotify.desktop")
                    stem = desktop_file.stem.lower().replace("_", " ").replace("-", " ")
                    for part in stem.split():
                        if len(part) > 2 and part not in app_map:
                            app_map[part] = desktop_file
            except Exception:
                continue

    logger.debug(f"Found {len(app_map)} applications")
    return app_map


def _parse_desktop_name(path: Path) -> str | None:
    """Parse the Name= field from a .desktop file."""
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                if line.startswith("Name="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def _find_app(query: str) -> Path | None:
    """Find the best matching .desktop file for a query.
    
    Supports fuzzy matching — "code" matches "Visual Studio Code",
    "brave" matches "Brave Web Browser", etc.
    """
    app_map = _get_app_map()
    query_lower = query.lower().strip()

    # Exact match
    if query_lower in app_map:
        return app_map[query_lower]

    # Substring match
    for name, path in app_map.items():
        if query_lower in name or name in query_lower:
            return path

    # Word-level match
    query_words = set(query_lower.split())
    for name, path in app_map.items():
        name_words = set(name.split())
        if query_words & name_words:
            return path

    return None


@registry.register
def open_application(app_name: str) -> str:
    """Open a desktop application by name.
    
    app_name: The application name (e.g., 'Brave', 'VS Code', 'Spotify', 'Telegram', 'Files')
    """
    desktop_file = _find_app(app_name)
    
    if desktop_file:
        result = subprocess.run(
            ["gio", "launch", str(desktop_file)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            app_display = _parse_desktop_name(desktop_file) or app_name
            return f"Launched {app_display}."
        else:
            return f"Failed to launch {app_name}: {result.stderr.strip()}"
    
    # Fallback: try launching by binary name
    try:
        subprocess.Popen(
            [app_name.lower()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launched {app_name}."
    except FileNotFoundError:
        return f"Could not find application '{app_name}'. Check the name and try again."


@registry.register
def close_application(app_name: str) -> str:
    """Close a running application by name.
    
    app_name: The application to close (e.g., 'Brave', 'Telegram', 'Spotify')
    """
    # Use wmctrl to find and close windows
    result = subprocess.run(
        ["wmctrl", "-l"], capture_output=True, text=True, timeout=5,
    )
    
    if result.returncode != 0:
        # Fallback: try pkill
        kill_result = subprocess.run(
            ["pkill", "-f", app_name.lower()],
            capture_output=True, text=True, timeout=5,
        )
        if kill_result.returncode == 0:
            return f"Closed {app_name}."
        return f"Could not find or close {app_name}."
    
    # Parse wmctrl output and close matching windows
    closed = False
    for line in result.stdout.strip().split("\n"):
        if app_name.lower() in line.lower():
            parts = line.split(None, 3)
            if parts:
                window_id = parts[0]
                subprocess.run(
                    ["wmctrl", "-i", "-c", window_id],
                    capture_output=True, text=True, timeout=5,
                )
                closed = True

    if closed:
        return f"Closed {app_name}."
    
    # Final fallback: pkill
    subprocess.run(
        ["pkill", "-f", app_name.lower()],
        capture_output=True, text=True, timeout=5,
    )
    return f"Sent close signal to {app_name}."


@registry.register
def list_running_apps() -> str:
    """List all currently open application windows."""
    result = subprocess.run(
        ["wmctrl", "-l"], capture_output=True, text=True, timeout=5,
    )
    
    if result.returncode != 0:
        # Fallback: use xdotool
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name", ""],
            capture_output=True, text=True, timeout=5,
        )
        return "Could not list running applications. wmctrl may not be installed."
    
    apps = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            parts = line.split(None, 3)
            if len(parts) >= 4:
                apps.append(parts[3])
    
    if apps:
        return "Open windows: " + ", ".join(apps)
    return "No open application windows found."


def invalidate_app_cache():
    """Clear the app map cache — call when apps are installed/removed."""
    _get_app_map.cache_clear()
