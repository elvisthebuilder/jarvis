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

from .config.settings import save_config

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

        # ── Phase 1: User Profile ──────────────────────────────────
        console.print("\n[bold cyan]Phase 1: User Profiling[/bold cyan]")
        
        title = await session.prompt_async("  What is your preferred title? [Default: Sir]: ", default="Sir")
        name = await session.prompt_async("  And your full name? [e.g. Tony Stark]: ", default="Tony Stark")
        aliases = await session.prompt_async("  Any aliases or social handles I should look for? [e.g. elvisthebuilder]: ", default="")
        occupation = await session.prompt_async("  And your primary occupation or role? [e.g. CEO of Stark Industries]: ", default="Engineer")
        interests = await session.prompt_async("  Any specific interests or goals for my assistance? [e.g. coding, research]: ", default="innovation")
        custom_context = await session.prompt_async("  Any additional context I should know about you? (Optional): ", default="")
        
        # ── Phase 2: Operations ────────────────────────────────────
        console.print("\n[bold cyan]Phase 2: Operational Credentials[/bold cyan]")
        console.print("  I require access to my neural backends to function.")
        
        ollama_key = await session.prompt_async("  Enter your Ollama Cloud (Gemma 4) API Key: ", is_password=True)
        gemini_key = await session.prompt_async("  Enter your Gemini Flash (Live Search) API Key: ", is_password=True)

        # ── Phase 3: Neural OSINT Sync ──────────────────────────────
        console.print("\n[bold cyan]Phase 3: Neural OSINT Synchronization[/bold cyan]")
        
        sync_choice = await session.prompt_async(
            "  Choose search intensity: [P]rofessional, [W]ide-net, or [S]kip [Default: P]: ", 
            default="P",
            is_password=False
        )
        
        osint_results = ""
        if sync_choice.upper() in ["P", "W"]:
            osint_results = await _perform_neural_sync(name, aliases, occupation, sync_choice.upper(), gemini_key)
            
            # Confirmation & Modification
            if osint_results:
                console.print("\n[bold cyan]Intelligence Briefing:[/bold cyan]")
                console.print(Panel(osint_results, border_style="dim white"))
                
                sync_action = await session.prompt_async(
                    "\n  Action: [A]ccept, [M]odify, or [D]ecline findings? [Default: A]: ", 
                    default="A"
                )
                
                if sync_action.upper() == "M":
                    # Allow the user to edit the findings directly in the terminal
                    console.print("\n[dim]Entering edit mode. You can modify the text below:[/dim]")
                    osint_results = await session.prompt_async(
                        "> ", 
                        default=osint_results, 
                        multiline=True
                    )
                    console.print("[bold green]✓ Briefing updated.[/bold green]")
                elif sync_action.upper() == "D":
                    osint_results = ""
                # If A (Accept), proceed with current osint_results
        
        # Combined context for the system prompt
        final_context = custom_context
        if osint_results:
            final_context = f"{custom_context}\n\nNeural Sync Briefing:\n{osint_results}"

        # ── Phase 4: Finalization ──────────────────────────────────
        updates = {
            "JARVIS_USER_TITLE": title,
            "JARVIS_USER_NAME": name,
            "JARVIS_USER_OCCUPATION": occupation,
            "JARVIS_USER_INTERESTS": interests,
            "JARVIS_USER_CONTEXT": final_context,
            "OLLAMA_API_KEY": ollama_key,
            "GEMINI_API_KEY": gemini_key,
            "ONBOARDING_COMPLETED": "true",
        }
        
        console.print("\n[bold yellow]Synchronizing core systems...[/bold yellow]")
        save_config(updates)
        
        # Simulate some Jarvis-like 'loading'
        with Live(Text("Uploading user profile...", style="dim white"), refresh_per_second=4) as live:
            await asyncio.sleep(0.8)
            live.update(Text("Mapping system permissions...", style="dim white"))
            await asyncio.sleep(0.8)
            live.update(Text("Finalizing neural handshake...", style="dim white"))
            await asyncio.sleep(0.8)

        console.print(Panel(
            f"[bold green]✓ Synchronization Complete.[/bold green]\n\n"
            f"Welcome home, {name}. I've configured my systems to your specifications.\n"
            f"You can now summon me with [bold cyan]Super + Shift + J[/bold cyan] at any time.",
            title="[bold cyan]✦ J.A.R.V.I.S.[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))
        
        console.print("\n[dim]Press Enter to start J.A.R.V.I.S. for the first time...[/dim]")
        await session.prompt_async("")
    except KeyboardInterrupt:
        return


async def _perform_neural_sync(name: str, aliases: str, occupation: str, scan_type: str, api_key: str) -> str:
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
            
            search_query = f"Search for {name} ({aliases}). They are a {occupation}. Find their socials, key projects, and public information for an AI assistant briefing."
            if scan_type == "W":
                search_query += " Cast a wide net including social media, blog posts, and fun facts."
            else:
                search_query += " Focus on professional accomplishments, LinkedIn, and GitHub."

            # Run search and ticker concurrently
            search_task = asyncio.create_task(_call_gemini_search(client, search_query))
            
            # Ticker loop
            idx = 1
            while not search_task.done():
                live.update(Text(statuses[idx % len(statuses)], style="dim cyan"))
                idx += 1
                await asyncio.sleep(1.5)
            
            return await search_task

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
