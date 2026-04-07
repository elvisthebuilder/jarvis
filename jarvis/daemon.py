"""Jarvis Daemon — the main entry point and event loop.

Initializes all components and provides both a CLI interactive mode
for testing and a D-Bus service mode for GNOME Shell integration.
"""

import os
import asyncio
import signal
import sys
import logging
from pathlib import Path
from datetime import datetime

from dbus_next.aio import MessageBus
from dbus_next import Message, MessageType

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from .config.settings import load_config, JarvisConfig
from .brain.agent import JarvisAgent
from .memory.store import MemoryStore
from .memory.preferences import PreferenceManager
from .dbus_service.server import start_dbus_service
from .onboarding import run_onboarding

logger = logging.getLogger("jarvis")

# Import tools to trigger registration
from .tools import registry as _  # noqa: F401
from .tools import media, apps, system, browser, notifications, clipboard, shell, files, realtime  # noqa: F401
from .tools.registry import registry

# ── Logging Setup ──────────────────────────────────────────

def setup_logging(config: JarvisConfig):
    """Configure structured logging."""
    log_dir = config.daemon.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.log"

    # File handler — detailed
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    ))

    # Console handler — minimal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)-7s | %(message)s"
    ))
    console_handler.setLevel(logging.WARNING)

    logging.basicConfig(
        level=getattr(logging, config.daemon.log_level),
        handlers=[file_handler, console_handler],
    )


# ── Rich Console Theme ─────────────────────────────────────

jarvis_theme = Theme({
    "jarvis": "bold cyan",
    "user": "bold green",
    "info": "dim white",
    "error": "bold red",
    "tool": "yellow",
})

console = Console(theme=jarvis_theme)


# ── ASCII Art Banner ────────────────────────────────────────

BANNER = """
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   Just A Rather Very Intelligent System
"""


# ── CLI Interactive Mode ────────────────────────────────────

async def run_cli(config: JarvisConfig):
    """Run Jarvis in interactive CLI mode for testing."""
    console.print(Panel(
        Text(BANNER, style="bold cyan", justify="center"),
        border_style="cyan",
        padding=(1, 2),
    ))
    
    console.print(f"  [info]Model: {config.ollama.model} via Ollama Cloud[/info]")
    console.print(f"  [info]Gemini: {'connected' if config.gemini.api_key else 'not configured'}[/info]")
    console.print(f"  [info]Tools: {len(registry.list_tools())} registered[/info]")
    console.print()

    # Initialize memory
    memory = MemoryStore(config.daemon.db_path)
    await memory.initialize()
    
    # Initialize preferences
    preferences = PreferenceManager(memory)
    await preferences.load_preferences()

    # Initialize agent
    agent = JarvisAgent(config, memory, preferences)

    # Get interaction count for first-time greeting
    interaction_count = await memory.get_interaction_count()
    
    if interaction_count == 0:
        console.print(Panel(
            f"[jarvis]Good evening, {config.user_title}. I am J.A.R.V.I.S.\n\n"
            "I'm your intelligent desktop companion. I can control your media,\n"
            "launch applications, adjust system settings, and much more.\n\n"
            "Just tell me what you need.[/jarvis]",
            title="[bold cyan]✦ J.A.R.V.I.S.[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))
    else:
        # Contextual greeting based on time
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = f"Good morning, {config.user_title}."
        elif 12 <= hour < 17:
            greeting = f"Good afternoon, {config.user_title}."
        elif 17 <= hour < 21:
            greeting = f"Good evening, {config.user_title}."
        else:
            greeting = f"Burning the midnight oil again, {config.user_title}?"
        
        console.print(f"\n  [jarvis]✦ {greeting} Ready when you are.[/jarvis]\n")

    # Set up command history
    history_path = config.daemon.data_dir / "cli_history"
    session = PromptSession(history=FileHistory(str(history_path)))

    # Main loop
    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt("\n  You → "),
            )

            if not user_input.strip():
                continue

            # Special commands
            cmd = user_input.strip().lower()
            if cmd in ("exit", "quit", "goodbye", "bye"):
                console.print("\n  [jarvis]✦ Goodbye, Sir. I'll be here when you need me.[/jarvis]\n")
                break
            if cmd == "/tools":
                tools = registry.list_tools()
                console.print(f"\n  [tool]Registered tools ({len(tools)}):[/tool]")
                for tool in tools:
                    console.print(f"    • {tool}")
                continue
            if cmd == "/clear":
                agent.new_session()
                console.print("\n  [info]Session cleared.[/info]")
                continue
            if cmd == "/status":
                count = await memory.get_interaction_count()
                prefs = await memory.get_all_preferences()
                console.print(f"\n  [info]Interactions: {count} | Preferences: {len(prefs)} | "
                            f"Session: {agent.session_id}[/info]")
                continue

            # Process with Jarvis
            console.print("\n  [info]⟳ thinking...[/info]", end="\r")
            
            response = await agent.process(user_input)
            
            # Clear the "thinking" line and display response
            console.print(f"  [jarvis]✦ {response}[/jarvis]")

        except KeyboardInterrupt:
            console.print("\n\n  [jarvis]✦ Interrupted. Type 'exit' to leave, Sir.[/jarvis]")
            continue
        except EOFError:
            console.print("\n  [jarvis]✦ Signing off, Sir.[/jarvis]\n")
            break
        except Exception as e:
            console.print(f"\n  [error]Error: {e}[/error]")
            logging.getLogger(__name__).exception("CLI error")

    # Cleanup
    await memory.close()


# ── Main Entry Point ────────────────────────────────────────

def main():
    """Main entry point for the Jarvis daemon."""
    # Parse mode from args
    mode = "cli"
    if "--daemon" in sys.argv:
        mode = "daemon"
    elif "--toggle" in sys.argv:
        mode = "toggle"

    # Load config
    config = load_config()
    setup_logging(config)

    logger.info(f"Jarvis starting in {mode} mode")

    if mode == "toggle":
        asyncio.run(run_toggle_command())
        sys.exit(0)

    # ── Check for Onboarding ──────────────────────────────────
    onboarding_done = os.getenv("ONBOARDING_COMPLETED", "false").lower() == "true"
    if not onboarding_done and mode == "cli":
        try:
            asyncio.run(run_onboarding())
            # Reload config after onboarding
            config = load_config()
        except KeyboardInterrupt:
            console.print("\n  [error]Onboarding interrupted. Please restart Jarvis, Sir.[/error]\n")
            sys.exit(1)
    elif not onboarding_done and mode == "daemon":
        logger.error("Onboarding not completed! Please run 'python -m jarvis.daemon' in your terminal first.")
        sys.exit(1)

    # Configure shell security
    shell.set_unrestricted(config.daemon.shell_unrestricted)

    if mode == "cli":
        # Interactive CLI mode
        try:
            asyncio.run(run_cli(config))
        except KeyboardInterrupt:
            console.print("\n  [jarvis]✦ Goodbye, Sir.[/jarvis]\n")
    else:
        # Daemon mode (D-Bus service) — Phase 2
        try:
            asyncio.run(run_daemon(config))
        except KeyboardInterrupt:
            logger.info("Daemon interrupted")
        except Exception as e:
            logger.error(f"Daemon crash: {e}")
            sys.exit(1)


async def run_daemon(config: JarvisConfig):
    """Run Jarvis as a background D-Bus service."""
    # Initialize components
    memory = MemoryStore(config.daemon.db_path)
    await memory.initialize()
    
    preferences = PreferenceManager(memory)
    await preferences.load_preferences()

    agent = JarvisAgent(config, memory, preferences)
    
    # Start D-Bus service
    logger.info("Starting D-Bus service...")
    await start_dbus_service(agent)
    
    # Cleanup on shutdown
    await memory.close()


async def run_toggle_command():
    """Send a D-Bus message to toggle the Jarvis UI."""
    try:
        bus = await MessageBus().connect()
        # Create a message to call the Toggle method on the Jarvis service
        msg = Message(
            destination='org.jarvis.Assistant',
            path='/org/jarvis/Assistant',
            interface='org.jarvis.Assistant',
            member='Toggle'
        )
        await bus.call(msg)
        logger.info("Toggle signal sent.")
    except Exception as e:
        logger.error(f"Failed to send toggle signal: {e}")
        print("Jarvis daemon doesn't seem to be running, Sir.")


if __name__ == "__main__":
    main()
