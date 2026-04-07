import subprocess
import logging
import urllib.parse
import time
import re

from .registry import registry

logger = logging.getLogger(__name__)


def _run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess command safely."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=check
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 1, "", "Timed out")
    except Exception as e:
        logger.error(f"Command failed: {' '.join(cmd)} — {e}")
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def _get_spotify_bus_name() -> str | None:
    """Find Spotify's MPRIS2 D-Bus name."""
    result = _run([
        "dbus-send", "--session", "--print-reply",
        "--dest=org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus.ListNames"
    ])
    if result.returncode == 0:
        for line in result.stdout.split("\n"):
            if "org.mpris.MediaPlayer2.spotify" in line:
                return "org.mpris.MediaPlayer2.spotify"
    return None


def _mpris_command(action: str, player: str = "spotify") -> str:
    """Send an MPRIS2 command to a media player via D-Bus."""
    bus_name = f"org.mpris.MediaPlayer2.{player}"
    result = _run([
        "dbus-send", "--session", "--print-reply",
        f"--dest={bus_name}",
        "/org/mpris/MediaPlayer2",
        f"org.mpris.MediaPlayer2.Player.{action}"
    ])
    return "success" if result.returncode == 0 else f"failed: {result.stderr.strip()}"


def _get_current_title() -> str:
    """Read the current title from Spotify metadata using dbus-send."""
    cmd = [
        "dbus-send", "--session", "--print-reply",
        "--dest=org.mpris.MediaPlayer2.spotify",
        "/org/mpris/MediaPlayer2",
        "org.freedesktop.DBus.Properties.Get",
        "string:org.mpris.MediaPlayer2.Player",
        "string:Metadata"
    ]
    result = _run(cmd)
    if result.returncode == 0:
        # Simple regex to find the title in the raw dbus output
        # Look for 'xesam:title' and capture the following string value
        match = re.search(r'string\s+"xesam:title"\s+variant\s+string\s+"([^"]+)"', result.stdout)
        if match:
            return match.group(1)
    return ""


def _wait_for_change(old_title: str, timeout: float = 3.0):
    """Wait for Spotify's metadata to reflect a song change before triggering Play."""
    if not old_title:
        time.sleep(1.2) # Basic fallback delay
        return

    start_time = time.time()
    while time.time() - start_time < timeout:
        new_title = _get_current_title()
        if new_title and new_title != old_title:
            logger.info(f"Metadata changed: '{old_title}' -> '{new_title}'. Ready to play.")
            return
        time.sleep(0.3)
    logger.info("Metadata poll timed out. Proceeding with Play attempt anyway.")


@registry.register
def play_spotify(query: str) -> str:
    """Play a song, artist, playlist, or library on Spotify.
    
    query: What to play — song title, artist name, 'my library', or 'playlist name'
    """
    query_lower = query.lower().strip()
    
    # Check for direct Library/Favorites requests
    if any(k in query_lower for k in ["my library", "liked songs", "favorites", "bookmarks"]):
        search_uri = "spotify:collection:tracks"
        query_type = "Music Library"
    elif "playlist" in query_lower:
        # If the user specifically mentions playlist, we keep using search but clarify type
        search_uri = f"spotify:search:{urllib.parse.quote(query)}"
        query_type = f"Playlist: {query}"
    else:
        search_uri = f"spotify:search:{urllib.parse.quote(query)}"
        query_type = f"Track: {query}"

    # First, try to open Spotify if not running
    spotify_bus = _get_spotify_bus_name()
    if not spotify_bus:
        logger.info("Spotify not running, launching it...")
        subprocess.Popen(
            ["spotify", "--uri", search_uri],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launched Spotify and opened your {query_type}."

    # Record current title only if Jarvis intends to 'Play' later
    old_title = _get_current_title()

    # Use Spotify URI search via DBus OpenUri
    result = _run([
        "dbus-send", "--session", "--print-reply",
        "--dest=org.mpris.MediaPlayer2.spotify",
        "/org/mpris/MediaPlayer2",
        "org.mpris.MediaPlayer2.Player.OpenUri",
        f"string:{search_uri}"
    ])

    if result.returncode == 0:
        # Wait for the search to register before sending 'Play'
        _wait_for_change(old_title)
        _mpris_command("Play")
        return f"Now playing your {query_type} on Spotify."
    else:
        # Fallback: launch Spotify with the search
        subprocess.Popen(
            ["spotify", "--uri", search_uri],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Opened Spotify with search for your {query_type}."


@registry.register
def pause_media() -> str:
    """Pause whatever music or media is currently playing."""
    # Try Spotify first, then any MPRIS player
    result = _mpris_command("Pause", "spotify")
    if "success" in result:
        return "Media paused."
    
    # Try playerctl as fallback
    fallback = _run(["playerctl", "pause"])
    if fallback.returncode == 0:
        return "Media paused."
    return "No active media player found to pause."


@registry.register
def resume_media() -> str:
    """Resume playing paused music or media."""
    result = _mpris_command("Play", "spotify")
    if "success" in result:
        return "Playback resumed."
    
    fallback = _run(["playerctl", "play"])
    if fallback.returncode == 0:
        return "Playback resumed."
    return "No paused media found to resume."


@registry.register
def next_track() -> str:
    """Skip to the next track."""
    result = _mpris_command("Next", "spotify")
    if "success" in result:
        return "Skipped to next track."
    
    fallback = _run(["playerctl", "next"])
    return "Skipped to next track." if fallback.returncode == 0 else "No media player found."


@registry.register
def previous_track() -> str:
    """Go back to the previous track."""
    result = _mpris_command("Previous", "spotify")
    if "success" in result:
        return "Went back to previous track."
    
    fallback = _run(["playerctl", "previous"])
    return "Previous track." if fallback.returncode == 0 else "No media player found."


@registry.register
def set_volume(level: int) -> str:
    """Set the system volume to a specific percentage.
    
    level: Volume percentage from 0 to 100
    """
    level = max(0, min(100, level))
    result = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
    if result.returncode == 0:
        return f"Volume set to {level}%."
    return f"Failed to set volume: {result.stderr.strip()}"


@registry.register
def get_volume() -> str:
    """Get the current system volume level."""
    result = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
    if result.returncode == 0:
        # Parse volume from output like "Volume: front-left: 65536 / 100% / 0.00 dB"
        for part in result.stdout.split("/"):
            part = part.strip()
            if "%" in part:
                return f"Current volume is {part}."
    return "Unable to determine current volume."


@registry.register
def mute_audio(mute: bool = True) -> str:
    """Mute or unmute system audio.
    
    mute: True to mute, False to unmute
    """
    value = "1" if mute else "0"
    result = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", value])
    if result.returncode == 0:
        return "Audio muted." if mute else "Audio unmuted."
    return "Failed to change mute state."


@registry.register
def get_now_playing() -> str:
    """Get information about the currently playing track."""
    result = _run(["playerctl", "metadata", "--format",
                    "{{artist}} - {{title}} ({{album}})"])
    if result.returncode == 0 and result.stdout.strip():
        status = _run(["playerctl", "status"])
        state = status.stdout.strip() if status.returncode == 0 else "Unknown"
        return f"Currently {state.lower()}: {result.stdout.strip()}"
    return "Nothing is currently playing."
