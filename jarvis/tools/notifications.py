"""Desktop notifications and reminders.

Uses notify-send for immediate notifications and asyncio timers for reminders.
"""

import asyncio
import subprocess
import logging
from datetime import datetime

from .registry import registry

logger = logging.getLogger(__name__)

# Active reminder tasks — so they can be cancelled if needed
_active_reminders: dict[str, asyncio.Task] = {}


@registry.register
def send_notification(title: str, body: str, urgency: str = "normal") -> str:
    """Show a desktop notification.
    
    title: The notification title/heading
    body: The notification message body
    urgency: Priority level — 'low', 'normal', or 'critical'
    """
    if urgency not in ("low", "normal", "critical"):
        urgency = "normal"

    result = subprocess.run(
        ["notify-send", f"--urgency={urgency}",
         "--app-name=Jarvis", title, body],
        capture_output=True, text=True, timeout=5,
    )

    if result.returncode == 0:
        return f"Notification sent: '{title}'."
    return f"Failed to send notification: {result.stderr.strip()}"


@registry.register
def create_reminder(message: str, minutes: int) -> str:
    """Set a reminder that will notify you after a specified number of minutes.
    
    message: What to remind about
    minutes: How many minutes from now to fire the reminder
    """
    if minutes <= 0:
        return "Reminder time must be positive."
    if minutes > 1440:  # 24 hours max
        return "Reminders cannot be set for more than 24 hours ahead."

    reminder_id = f"reminder_{datetime.now().strftime('%H%M%S')}_{minutes}"
    
    async def _fire_reminder():
        await asyncio.sleep(minutes * 60)
        subprocess.run(
            ["notify-send", "--urgency=critical",
             "--app-name=Jarvis",
             "⏰ Reminder from Jarvis",
             message],
            capture_output=True, text=True, timeout=5,
        )
        logger.info(f"Reminder fired: {message}")
        _active_reminders.pop(reminder_id, None)

    try:
        loop = asyncio.get_event_loop()
        task = loop.create_task(_fire_reminder())
        _active_reminders[reminder_id] = task
    except RuntimeError:
        # Not in async context — schedule for later
        logger.warning("Could not schedule reminder — no running event loop")
        return "Failed to set reminder. The daemon may not be running in async mode."

    if minutes == 1:
        return f"Reminder set. I'll notify you in 1 minute: '{message}'."
    elif minutes < 60:
        return f"Reminder set. I'll notify you in {minutes} minutes: '{message}'."
    else:
        hours = minutes // 60
        remaining_mins = minutes % 60
        time_str = f"{hours}h {remaining_mins}m" if remaining_mins else f"{hours}h"
        return f"Reminder set. I'll notify you in {time_str}: '{message}'."


@registry.register
def list_reminders() -> str:
    """List all currently active reminders."""
    if not _active_reminders:
        return "No active reminders."
    
    reminders = []
    for rid in _active_reminders:
        parts = rid.split("_")
        reminders.append(f"- Set at {parts[1]}, {parts[2]}min delay")
    
    return "Active reminders:\n" + "\n".join(reminders)


@registry.register
def cancel_all_reminders() -> str:
    """Cancel all pending reminders."""
    count = len(_active_reminders)
    for task in _active_reminders.values():
        task.cancel()
    _active_reminders.clear()
    
    if count == 0:
        return "No reminders to cancel."
    return f"Cancelled {count} reminder(s)."
