import os
"""System controls — brightness, dark mode, night light, battery, lock, and system info.

Uses gsettings for GNOME preferences, D-Bus for UPower/screensaver,
and /sys for hardware controls.
"""

import subprocess
import logging
from pathlib import Path
import urllib.request
import json

import psutil

from .registry import registry

logger = logging.getLogger(__name__)


def _gsettings_set(schema: str, key: str, value: str) -> bool:
    """Set a GNOME gsettings value."""
    result = subprocess.run(
        ["gsettings", "set", schema, key, value],
        capture_output=True, text=True, timeout=5,
    )
    return result.returncode == 0


def _gsettings_get(schema: str, key: str) -> str | None:
    """Get a GNOME gsettings value."""
    result = subprocess.run(
        ["gsettings", "get", schema, key],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else None


@registry.register
def get_brightness() -> int:
    """Get the current screen brightness percentage."""
    result = subprocess.run(
        ["gdbus", "call", "--session",
         "--dest", "org.gnome.SettingsDaemon.Power",
         "--object-path", "/org/gnome/SettingsDaemon/Power",
         "--method", "org.freedesktop.DBus.Properties.Get",
         "org.gnome.SettingsDaemon.Power.Screen",
         "Brightness"],
        capture_output=True, text=True, timeout=5,
    )

    if result.returncode == 0:
        # Output is like: (variant int32 80,)
        try:
            return int(result.stdout.split()[-1].strip("(),"))
        except (IndexError, ValueError):
            pass

    # Fallback to brightnessctl
    result = subprocess.run(["brightnessctl", "get"], capture_output=True, text=True)
    if result.returncode == 0:
        curr = int(result.stdout.strip())
        result_max = subprocess.run(["brightnessctl", "max"], capture_output=True, text=True)
        if result_max.returncode == 0:
            max_p = int(result_max.stdout.strip())
            return int(curr * 100 / max_p)

    return 50  # Default fallback


@registry.register
def set_brightness(level: int) -> str:
    """Set the screen brightness to a specific percentage.
    
    level: Brightness percentage from 5 to 100
    """
    level = max(5, min(100, level))

    # Try GNOME D-Bus method first
    result = subprocess.run(
        ["gdbus", "call", "--session",
         "--dest", "org.gnome.SettingsDaemon.Power",
         "--object-path", "/org/gnome/SettingsDaemon/Power",
         "--method", "org.freedesktop.DBus.Properties.Set",
         "org.gnome.SettingsDaemon.Power.Screen",
         "Brightness",
         f"<int32 {level}>"],
        capture_output=True, text=True, timeout=5,
    )

    if result.returncode == 0:
        return f"Brightness set to {level}%."

    # Fallback: try /sys/class/backlight
    backlight_dirs = list(Path("/sys/class/backlight").glob("*"))
    if backlight_dirs:
        bl = backlight_dirs[0]
        try:
            max_brightness_val = int((bl / "max_brightness").read_text().strip())
            target = int(max_brightness_val * level / 100)
            (bl / "brightness").write_text(str(target))
            return f"Brightness set to {level}%."
        except PermissionError:
            # Fallback 2: Direct sysfs via pkexec (will show GUI password prompt)
            try:
                # Finding the backlight device name dynamically
                backlight_path = "/sys/class/backlight"
                devices = os.listdir(backlight_path)
                if devices:
                    device = devices[0]
                    max_brightness = int(open(f"{backlight_path}/{device}/max_brightness").read())
                    target = int((level / 100) * max_brightness)
                    subprocess.run(["pkexec", "sh", "-c", f"echo {target} > {backlight_path}/{device}/brightness"], check=True)
                    return f"Brightness set to {level}% (via pkexec)."
            except Exception as e:
                logger.debug(f"pkexec fallback failed: {e}")

    # Fallback 3: brightnessctl
    result = subprocess.run(["brightnessctl", "set", f"{level}%"], capture_output=True, text=True)
    if result.returncode == 0:
        return f"Brightness set to {level}%."

    return "Unable to set brightness. You may need to log out/in for group changes to take effect, or check permissions."


@registry.register
def close_browsers() -> str:
    """Close all open web browsers (Chrome, Firefox, Brave, and Edge)."""
    browsers = ["chrome", "firefox", "brave", "edge", "chromium", "browser"]
    closed = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            name = (proc.info['name'] or "").lower()
            cmdline = " ".join(proc.info['cmdline'] if proc.info['cmdline'] else []).lower()
            
            for b in browsers:
                if b in name or b in cmdline:
                    proc.terminate()
                    if name not in closed:
                        closed.append(name)
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if closed:
        return f"Closed the following browser processes: {', '.join(set(closed))}."
    return "No active browsers found to close."


@registry.register
def toggle_dark_mode() -> str:
    """Toggle between light and dark mode in GNOME."""
    current = _gsettings_get("org.gnome.desktop.interface", "color-scheme")
    
    if current and "dark" in current:
        _gsettings_set("org.gnome.desktop.interface", "color-scheme", "'default'")
        _gsettings_set("org.gnome.desktop.interface", "gtk-theme", "'Adwaita'")
        return "Switched to light mode."
    else:
        _gsettings_set("org.gnome.desktop.interface", "color-scheme", "'prefer-dark'")
        _gsettings_set("org.gnome.desktop.interface", "gtk-theme", "'Adwaita-dark'")
        return "Switched to dark mode."


@registry.register
def set_dark_mode(enabled: bool) -> str:
    """Enable or disable dark mode.
    
    enabled: True for dark mode, False for light mode
    """
    if enabled:
        _gsettings_set("org.gnome.desktop.interface", "color-scheme", "'prefer-dark'")
        _gsettings_set("org.gnome.desktop.interface", "gtk-theme", "'Adwaita-dark'")
        return "Dark mode enabled."
    else:
        _gsettings_set("org.gnome.desktop.interface", "color-scheme", "'default'")
        _gsettings_set("org.gnome.desktop.interface", "gtk-theme", "'Adwaita'")
        return "Light mode enabled."


@registry.register
def set_night_light(enabled: bool) -> str:
    """Enable or disable the night light (blue light filter).
    
    enabled: True to enable, False to disable
    """
    value = "true" if enabled else "false"
    success = _gsettings_set("org.gnome.settings-daemon.plugins.color", "night-light-enabled", value)
    
    if success:
        return "Night light enabled." if enabled else "Night light disabled."
    return "Failed to change night light setting."


@registry.register
def get_battery_status() -> str:
    """Get the current battery level and charging status."""
    battery = psutil.sensors_battery()
    
    if battery is None:
        return "No battery detected — this appears to be a desktop system."
    
    percent = round(battery.percent)
    plugged = "charging" if battery.power_plugged else "on battery"
    
    if battery.secsleft > 0 and not battery.power_plugged:
        hours = battery.secsleft // 3600
        minutes = (battery.secsleft % 3600) // 60
        time_left = f", approximately {hours}h {minutes}m remaining"
    else:
        time_left = ""
    
    return f"Battery is at {percent}%, currently {plugged}{time_left}."


@registry.register
def lock_screen() -> str:
    """Lock the screen immediately."""
    result = subprocess.run(
        ["dbus-send", "--session", "--type=method_call",
         "--dest=org.gnome.ScreenSaver",
         "/org/gnome/ScreenSaver",
         "org.gnome.ScreenSaver.Lock"],
        capture_output=True, text=True, timeout=5,
    )
    
    if result.returncode == 0:
        return "Screen locked."
    
    # Fallback
    subprocess.run(["gnome-screensaver-command", "-l"],
                   capture_output=True, text=True, timeout=5)
    return "Screen locked."


@registry.register
def get_system_info() -> str:
    """Get current system resource usage — CPU, RAM, and disk."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    mem_used = memory.used / (1024 ** 3)
    mem_total = memory.total / (1024 ** 3)
    disk_used = disk.used / (1024 ** 3)
    disk_total = disk.total / (1024 ** 3)
    
    return (
        f"CPU: {cpu_percent}% | "
        f"RAM: {mem_used:.1f}/{mem_total:.1f} GB ({memory.percent}%) | "
        f"Disk: {disk_used:.0f}/{disk_total:.0f} GB ({disk.percent}%)"
    )


@registry.register
def set_do_not_disturb(enabled: bool) -> str:
    """Enable or disable do not disturb mode (suppresses notifications).
    
    enabled: True to enable DND, False to disable
    """
    value = "true" if enabled else "false"
    success = _gsettings_set("org.gnome.desktop.notifications", "show-banners", 
                              "false" if enabled else "true")
    if success:
        return "Do not disturb enabled." if enabled else "Do not disturb disabled."
    return "Failed to change notification settings."


@registry.register
def get_current_location() -> str:
    """Get the current physical location (city, region, country) based on IP address.
    Use this when you need location data for weather or local time.
    """
    try:
        req = urllib.request.Request("http://ip-api.com/json/", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data['status'] == 'success':
                return f"Current location: {data['city']}, {data['regionName']}, {data['country']}"
            return "Could not determine location from IP."
    except Exception as e:
        logger.error(f"Location lookup failed: {e}")
        return "Failed to retrieve location due to network error."

