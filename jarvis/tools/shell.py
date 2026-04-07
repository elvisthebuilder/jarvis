"""Shell command execution — sandboxed by default.

Provides safe command execution with a whitelist of allowed commands.
Full shell access can be enabled in configuration.
"""

import subprocess
import shlex
import logging

from .registry import registry

logger = logging.getLogger(__name__)

# Default whitelist of safe, read-only commands
DEFAULT_WHITELIST = {
    "ls", "cat", "head", "tail", "wc", "grep", "find", "date", "cal",
    "df", "du", "free", "uptime", "whoami", "hostname", "uname",
    "echo", "pwd", "which", "file", "stat", "md5sum", "sha256sum",
    "tree", "sort", "uniq", "tr", "cut", "awk", "sed",
    "ip", "ss", "ping", "dig", "nslookup",
    "python3", "node", "git",
}

# Commands that are ALWAYS blocked
BLOCKED_COMMANDS = {
    "rm", "rmdir", "mkfs", "dd", "format",
    "shutdown", "reboot", "poweroff", "halt", "init",
    "chmod", "chown", "chgrp",
    "su", "sudo", "doas",
    "curl", "wget",  # network access should go through specific tools
}

# Whether unrestricted mode is enabled (set from config)
_unrestricted = False


def set_unrestricted(enabled: bool):
    """Enable or disable unrestricted shell access."""
    global _unrestricted
    _unrestricted = enabled
    if enabled:
        logger.warning("Shell unrestricted mode enabled — all commands allowed")


def _is_command_allowed(command: str) -> tuple[bool, str]:
    """Check if a command is allowed to run.
    
    Returns:
        (allowed, reason) tuple
    """
    if _unrestricted:
        # Even in unrestricted mode, block destructive system commands
        try:
            parts = shlex.split(command)
        except ValueError:
            return False, "Invalid command syntax"
        
        base_cmd = parts[0] if parts else ""
        if base_cmd in BLOCKED_COMMANDS:
            return False, f"Command '{base_cmd}' is always blocked for safety"
        return True, "Unrestricted mode"

    # Parse the command to get the base command
    try:
        parts = shlex.split(command)
    except ValueError:
        return False, "Invalid command syntax"

    if not parts:
        return False, "Empty command"

    base_cmd = parts[0]
    
    # Check against blocked list first
    if base_cmd in BLOCKED_COMMANDS:
        return False, f"Command '{base_cmd}' is blocked for safety"

    # Check against whitelist
    if base_cmd not in DEFAULT_WHITELIST:
        return False, f"Command '{base_cmd}' is not in the allowed list"

    # Check for pipe/redirect exploits
    dangerous_chars = [";", "&&", "||", "`", "$(", ">", ">>", "<"]
    for char in dangerous_chars:
        if char in command:
            return False, f"Command contains disallowed operator: {char}"

    return True, "Whitelisted command"


@registry.register
def run_shell_command(command: str) -> str:
    """Execute a shell command and return its output.
    
    command: The shell command to run (must be a safe, whitelisted command)
    """
    allowed, reason = _is_command_allowed(command)
    
    if not allowed:
        return f"Command blocked: {reason}. Ask Sir if you need shell access to be expanded."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(__import__("pathlib").Path.home()),
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            if error:
                return f"Command exited with code {result.returncode}: {error[:500]}"
            return f"Command exited with code {result.returncode}"

        if not output:
            return "Command completed successfully (no output)."
        
        # Truncate very long output
        if len(output) > 2000:
            return output[:2000] + f"\n... (output truncated, {len(output)} total characters)"
        
        return output

    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Command failed: {type(e).__name__}: {e}"
