"""J.A.R.V.I.S. Onboarding — the 'Stark Interview' experience.

Conducts an interactive terminal session to learn about the user
and configure critical API credentials.
"""

import sys
import os
import asyncio
import json
from typing import Dict, List, Optional
from google import genai
from google.genai import types as genai_types

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.live import Live
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

from .config.settings import save_config, _load_dotenv
from .utils.resilience import retry_async

console = Console()

INTERVIEW_STYLE = Style.from_dict({
    'prompt': 'bold cyan',
    'input': 'white',
})

async def run_onboarding():
    """Run the interactive onboarding session."""
    try:
        session = PromptSession(style=INTERVIEW_STYLE)
        
        console.clear()
        
        # ── Welcome Banner ──────────────────────────────────────────
        banner = Text("\nJ.A.R.V.I.S. SYSTEM INITIALIZATION\n", style="bold cyan")
        console.print(Panel(
            Text.assemble(
                banner,
                "\nInitializing the Just A Rather Very Intelligent System...\n",
                "I require a brief interview to synchronize with my primary user.",
            ),
            border_style="cyan",
            padding=(1, 2),
        ))

        # Check for elective re-onboarding
        target_dir = os.path.expanduser("~/.local/share/jarvis")
        env_path = os.path.join(target_dir, ".env")
        env_exists = os.path.exists(env_path)
        
        phases_to_run = ["1", "2", "3"]
        if env_exists:
            # Load existing config so later phases have context
            from pathlib import Path
            _load_dotenv(Path(env_path))
            
            console.print("\n[bold yellow]! Existing configuration detected.[/bold yellow]")
            console.print("  Sir, you may choose specific neural modules to re-synchronize.")
            console.print("  [1] Profile Update  [2] Credentials Sync  [3] Neural OSINT dossier")
            
            try:
                choice = await session.prompt_async(
                    "  Selection (e.g., 1,3 or Enter for all): ", 
                    default="1,2,3"
                )
                phases_to_run = [p.strip() for p in choice.split(",") if p.strip()]
            except KeyboardInterrupt:
                return
            
            if not phases_to_run:
                console.print("\n[bold green]✓ Neural handshake remains intact. No changes requested.[/bold green]\n")
                return

        # ── Data Accumulator ────────────────────────────────────────
        # We start with empty or current values depending on existing config
        # (For now, we'll initialize with defaults as the manual update rule is only on success)
        updates = {}

        # ── Phase 1: User Profile ──────────────────────────────────
        if "1" in phases_to_run:
            console.print("\n[bold cyan]Phase 1: User Profiling[/bold cyan]")
            
            title = await session.prompt_async("  What is your preferred title? [Default: Sir]: ", default="Sir")
            name = await session.prompt_async("  And your full name? [e.g. Tony Stark]: ", default="Tony Stark")
            aliases = await session.prompt_async("  Any aliases or social handles I should look for? [e.g. elvisthebuilder]: ", default="")
            occupation = await session.prompt_async("  And your primary occupation or role? [e.g. CEO of Stark Industries]: ", default="Engineer")
            interests = await session.prompt_async("  Any specific interests or goals for my assistance? [e.g. coding, research]: ", default="innovation")
            custom_context = await session.prompt_async("  Any additional context I should know about you? (Optional): ", default="")
            
            updates.update({
                "JARVIS_USER_TITLE": title,
                "JARVIS_USER_NAME": name,
                "JARVIS_USER_HANDLE": aliases,
                "JARVIS_USER_OCCUPATION": occupation,
                "JARVIS_USER_INTERESTS": interests,
                "JARVIS_USER_CONTEXT": custom_context,
            })
        
        # ── Phase 2: Operations ────────────────────────────────────
        if "2" in phases_to_run:
            console.print("\n[bold cyan]Phase 2: Operational Credentials[/bold cyan]")
            console.print("  I require access to my neural backends to function.")
            
            ollama_key = await session.prompt_async("  Enter your Ollama Cloud (Gemma 4) API Key: ", is_password=True)
            gemini_key = await session.prompt_async("  Enter your Gemini Flash (Live Search) API Key: ", is_password=True)
            
            updates.update({
                "OLLAMA_API_KEY": ollama_key,
                "GEMINI_API_KEY": gemini_key,
            })

        # ── Phase 3: Neural OSINT Sync ──────────────────────────────
        if "3" in phases_to_run:
            console.print("\n[bold cyan]Phase 3: Neural OSINT Synchronization[/bold cyan]")
            
            sync_choice = await session.prompt_async(
                "  Choose reconnaissance intensity: [R]apid (500 sites), [D]eep (3000+ sites), or [S]kip [Default: R]: ", 
                default="R",
                is_password=False
            )
            
            osint_results = ""
            if sync_choice.upper() in ["R", "D"]:
                # Use current name/aliases/key if various phases were skipped
                p_name = updates.get("JARVIS_USER_NAME") or os.getenv("JARVIS_USER_NAME", "User")
                p_aliases = updates.get("JARVIS_USER_HANDLE") or os.getenv("JARVIS_USER_HANDLE", "")
                p_gemini = updates.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
                
                email = await session.prompt_async("  Enter your primary email for deep verification (Optional): ", default="")
                
                osint_results = await _perform_neural_sync(p_name, p_aliases, email, sync_choice.upper(), p_gemini)
                
                # Confirmation & Modification
                if osint_results:
                    console.print("\n[bold cyan]Intelligence Briefing:[/bold cyan]")
                    console.print(Panel(osint_results, border_style="dim white"))
                    
                    sync_action = await session.prompt_async(
                        "\n  Action: [A]ccept, [M]odify, or [D]ecline findings? [Default: A]: ", 
                        default="A"
                    )
                    
                    if sync_action.upper() == "M":
                        console.print("\n[dim]Entering edit mode. You can modify the text below:[/dim]")
                        osint_results = await session.prompt_async("> ", default=osint_results, multiline=True)
                        console.print("[bold green]✓ Briefing updated.[/bold green]")
                    elif sync_action.upper() == "D":
                        osint_results = ""
                
                if osint_results:
                    # Update context with briefing
                    base_ctx = updates.get("JARVIS_USER_CONTEXT", os.getenv("JARVIS_USER_CONTEXT", ""))
                    updates["JARVIS_USER_CONTEXT"] = f"{base_ctx}\n\nNeural Sync Briefing:\n{osint_results}"

        # ── Phase 4: Finalization ──────────────────────────────────
        if updates:
            updates["ONBOARDING_COMPLETED"] = "true"
            console.print("\n[bold yellow]Synchronizing core systems...[/bold yellow]")
            save_config(updates)
            
            with Live(Text("Uploading user profile...", style="dim white"), refresh_per_second=4) as live:
                await asyncio.sleep(0.8)
                live.update(Text("Mapping system permissions...", style="dim white"))
                await asyncio.sleep(0.8)
                live.update(Text("Finalizing neural handshake...", style="dim white"))
                await asyncio.sleep(0.8)

            console.print(Panel(
                f"[bold green]✓ Synchronization Complete.[/bold green]\n\n"
                f"I've configured my systems to your specifications.\n"
                f"You can now summon me with [bold cyan]Super + Shift + J[/bold cyan] at any time.",
                title="[bold cyan]✦ J.A.R.V.I.S.[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            ))
        
        console.print("\n[dim]Press Enter to continue...[/dim]")
        await session.prompt_async("")
    except KeyboardInterrupt:
        return


async def _perform_neural_sync(name: str, usernames: str, email: str, scan_type: str, api_key: str) -> str:
    """Perform the actual web search and intelligence briefing."""
    if not api_key:
        return ""

    # Status messages for the ticker
    statuses = [
        "Initializing neural handshake...",
        "Bypassing public firewalls...",
        "Scraping professional networks...",
        "Analyzing digital footprint...",
        "Cross-referencing GitHub commits...",
        "Searching for 'elvisthebuilder' aliases...",
        "Connecting Ikigai philosophical alignment...",
        "Almost complete...",
    ]
    
    with Live(Text(statuses[0], style="dim cyan"), refresh_per_second=4) as live:
        try:
            # Construct the search task
            client = genai.Client(api_key=api_key)
            
            # 1. Perform Technical Recon (Username + Email)
            from .tools.osint import lookup_username_footprint, lookup_email_footprint
            
            recon_tasks = []
            if usernames:
                primary_handle = usernames.split(",")[0].strip()
                scan_depth = "deep" if scan_type == "D" else "rapid"
                recon_tasks.append(lookup_username_footprint(primary_handle, scan_depth))
            
            if email:
                recon_tasks.append(lookup_email_footprint(email))
            
            recon_data = ""
            if recon_tasks:
                live.update(Text("󰓦 Initiating neural reconnaissance sweep...", style="dim cyan"))
                recon_results = await asyncio.gather(*recon_tasks)
                recon_data = "\n\n".join(recon_results)

            # 2. Synthesize Intelligence with Gemini
            live.update(Text("󰔦 Synthesizing intelligence briefing...", style="dim cyan"))
            
            search_query = (
                f"I've conducted a deep reconnaissance for {name}. "
                f"Known handles: {usernames}. "
            )
            if recon_data:
                search_query += f"\nFound Data Points:\n{recon_data}\n"
            
            search_query += (
                "\nPlease summarize these findings into a professional 'Intelligence Brief' for the user. "
                "Combine these technical data points with any other relevant public info you can locate."
            )

            # Run search and ticker concurrently
            async def _on_retry(attempt, total, err):
                live.update(Text(f"󰚰 Negotiating neural bottleneck... (Attempt {attempt}/{total})", style="bold yellow"))
                await asyncio.sleep(1.0) # brief extra pause

            return await retry_async(
                _call_gemini_search,
                max_retries=3,
                initial_delay=2.0,
                on_retry_callback=_on_retry,
                client=client,
                query=search_query
            )

        except Exception as e:
            if 'live' in locals():
                live.update(Text(f"Error: {str(e)}", style="bold red"))
            return ""

async def _call_gemini_search(client: genai.Client, query: str) -> str:
    """Internal helper to call Gemini's search grounding asynchronously with J.A.R.V.I.S. persona."""
    try:
        system_instruction = (
            "You are J.A.R.V.I.S., a sophisticated AI assistant. You have just conducted a global "
            "intelligence sweep for your primary user. Present your findings as an 'Intelligence Brief'. "
            "Address the user formally (as 'Sir'). Be professional, efficient, and slightly protective. "
            "If you find information, present it as 'I have located the following data points...'. "
            "If you find nothing, explain that you were unable to find a direct match but mention any interesting leads. "
            "Use clear bullet points for data, but keep the overall tone conversational and distinctly J.A.R.V.I.S.-like. "
            "Do not include generic AI disclaimers or introductory filler like 'As a professional analyst...'"
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            ),
        )
        return response.text or "No information located."
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            return "OSINT synchronization paused: Gemini API quota exceeded for the free tier. I will rely on the manually provided profile info, Sir."
        return f"OSINT failed: {error_msg}"


if __name__ == "__main__":
    asyncio.run(run_onboarding())
