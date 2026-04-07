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

import argparse
import subprocess

# ── Main Entry Point ────────────────────────────────────────

def main():
    """Main entry point for the J.A.R.V.I.S. Command & Memory Suite."""
    # Determine project root dynamically (package is in <root>/jarvis)
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent
    scripts_dir = project_root / "scripts"

    parser = argparse.ArgumentParser(
        description="J.A.R.V.I.S. — Just A Rather Very Intelligent System",
        prog="jarvis"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Management commands")
    
    # jarvis onboard
    subparsers.add_parser("onboard", help="Initiate the Stark Interview (re-profiling)")
    
    # jarvis update
    subparsers.add_parser("update", help="Synchronize with the latest core code")
    
    # jarvis uninstall
    subparsers.add_parser("uninstall", help="Cleanly decommission J.A.R.V.I.S. from this system")
    
    # jarvis stop/restart
    subparsers.add_parser("stop", help="Shutdown the background daemon")
    subparsers.add_parser("restart", help="Restart the background daemon")
    subparsers.add_parser("status", help="Check J.A.R.V.I.S. vitals and service state")
    
    # Default behavior options (when no subcommand is used)
    parser.add_argument("--daemon", action="store_true", help="Start as a background D-Bus service")
    parser.add_argument("--toggle", action="store_true", help="Toggle the UI overlay")
    parser.add_argument("--incognito", action="store_true", help="Start a private session (no context/logging)")
    
    args = parser.parse_args()

    # Handle Subcommands
    if args.command == "onboard":
        try:
            asyncio.run(run_onboarding())
        except KeyboardInterrupt:
            console.print("\n  [error]Onboarding interrupted. Please restart J.A.R.V.I.S., Sir.[/error]\n")
            sys.exit(1)
        sys.exit(0)
    elif args.command == "update":
        script_path = scripts_dir / "update.sh"
        if script_path.exists():
            subprocess.run(["bash", str(script_path)], cwd=str(project_root))
        else:
            print(f"Error: Management script {script_path} not found, Sir.")
        sys.exit(0)
    elif args.command == "uninstall":
        script_path = scripts_dir / "uninstall.sh"
        if script_path.exists():
            subprocess.run(["bash", str(script_path)], cwd=str(project_root))
        else:
            print(f"Error: Management script {script_path} not found, Sir.")
        sys.exit(0)
    elif args.command in ["stop", "restart", "status"]:
        cmd = ["systemctl", "--user", args.command, "jarvis"]
        if args.command == "status":
            subprocess.run(cmd)
        else:
            subprocess.run(cmd)
            print(f"Deployment command '{args.command}' executed successfully, Sir.")
        sys.exit(0)

    # Standard Execution Logic
    mode = "daemon" if args.daemon else ("toggle" if args.toggle else "cli")
    
    # Load config and setup logging
    config = load_config()
    setup_logging(config)

    if mode == "toggle":
        asyncio.run(run_toggle_command())
        sys.exit(0)

    # ── Check for Onboarding ──────────────────────────────────
    onboarding_done = os.getenv("ONBOARDING_COMPLETED", "false").lower() == "true"
    if not onboarding_done and mode == "cli":
        try:
            asyncio.run(run_onboarding())
            config = load_config()
        except KeyboardInterrupt:
            console.print("\n  [error]Onboarding interrupted. Please restart Jarvis, Sir.[/error]\n")
            sys.exit(1)
    elif not onboarding_done and mode == "daemon":
        logger.error("Onboarding not completed! Please run 'jarvis' in your terminal first.")
        sys.exit(1)

    # Configure shell security
    shell.set_unrestricted(config.daemon.shell_unrestricted)

    if mode == "cli":
        # Interactive CLI mode
        try:
            # Initialize Assistant Core with optional memory sync
            memory = MemoryStore(config.daemon.db_path)
            asyncio.run(memory.initialize())
            
            preferences = PreferenceManager(memory)
            asyncio.run(preferences.load_preferences())
            
            agent = JarvisAgent(config, memory, preferences)
            
            if args.incognito:
                agent.set_incognito(True)
            else:
                # Total Recall: Load historical context
                asyncio.run(agent.load_last_context(limit=5))
            
            asyncio.run(run_cli_with_agent(agent, config))
        except KeyboardInterrupt:
            console.print("\n  [jarvis]✦ Goodbye, Sir.[/jarvis]\n")
        finally:
            if 'memory' in locals():
                asyncio.run(memory.close())
    else:
        # Daemon mode
        try:
            asyncio.run(run_daemon(config))
        except KeyboardInterrupt:
            logger.info("Daemon interrupted")
        except Exception as e:
            logger.error(f"Daemon crash: {e}")
            sys.exit(1)


async def run_cli_with_agent(agent: JarvisAgent, config: JarvisConfig):
    """Run Jarvis in interactive CLI mode with a neural-linked agent."""
    console.print(Panel(
        Text(BANNER, style="bold cyan", justify="center"),
        border_style="cyan",
        title="[bold white]Command Central[/bold white]",
        subtitle="[dim]Neural Link Established[/dim]",
        padding=(1, 2)
    ))
    
    # Contextual greeting based on time (only if not incognito)
    if not agent._incognito:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = f"Good morning, {config.user_title}."
        elif 12 <= hour < 17:
            greeting = f"Good afternoon, {config.user_title}."
        elif 17 <= hour < 21:
            greeting = f"Good evening, {config.user_title}."
        else:
            greeting = f"Burning the midnight oil again, {config.user_title}?"
        
        console.print(f"  [jarvis]✦ {greeting} Ready when you are.[/jarvis]\n")
    else:
        console.print("  [jarvis]✦ Incognito session started. I am listening, Sir.[/jarvis]\n")

    # Set up command history (shell history, not conversation history)
    history_path = config.daemon.data_dir / "cli_history"
    session = PromptSession(history=FileHistory(str(history_path)))

    # Main loop
    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt("  You → "),
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
                count = await agent.memory.get_interaction_count()
                prefs = await agent.memory.get_all_preferences()
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


async def run_daemon(config: JarvisConfig):
    """Run Jarvis as a background D-Bus service with Total Recall enabled."""
    # Initialize components
    memory = MemoryStore(config.daemon.db_path)
    await memory.initialize()
    
    preferences = PreferenceManager(memory)
    await preferences.load_preferences()

    agent = JarvisAgent(config, memory, preferences)
    
    # Total Recall: Load history before starting service
    await agent.load_last_context(limit=5)
    
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
