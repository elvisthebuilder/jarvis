import asyncio
import logging
from typing import List, Dict, Any

# Maigret - username recon
try:
    from maigret import MaigretExecutor, MaigretDatabase
    MAIGRET_AVAILABLE = True
except ImportError:
    MAIGRET_AVAILABLE = False

# Holehe - email footprint
try:
    from holehe import core as holehe_core
    HOLEHE_AVAILABLE = True
except ImportError:
    HOLEHE_AVAILABLE = False

from .registry import registry

logger = logging.getLogger(__name__)

@registry.register
async def lookup_username_footprint(username: str, scan_depth: str = "rapid") -> str:
    """Perform a deep reconnaissance of a username across thousands of sites.
    
    Use this to find a person's digital dossier, including social media profiles,
    biographies, and technical contributions.
    
    username: The handle/username to investigate (e.g. 'elvisthebuilder')
    scan_depth: 'rapid' scanning the top 500 sites, or 'deep' scanning 3000+ sites.
    """
    if not MAIGRET_AVAILABLE:
        return "Username reconnaissance (Maigret) is not installed in the current environment, Sir."

    try:
        db = MaigretDatabase().load_from_path() # uses internal default
        # Filter sites based on depth
        if scan_depth.lower() == "deep":
            sites = db.sites
        else:
            # Simple heuristic for 'rapid': sites with higher rank/popularity if available
            # Or just limit the list for proof of concept
            sites = [s for s in db.sites if s.name in ("github", "twitter", "linkedin", "instagram", "reddit", "medium")]
            if len(sites) < 10: # Fallback to a slice if manual filter too small
                sites = list(db.sites.values())[:300]
        
        executor = MaigretExecutor(db, username=username)
        
        # Start scanning
        results = []
        async for result in executor.run(sites=sites):
            if result.status == "found":
                results.append(f"- {result.site.name}: {result.url}")

        if not results:
            return f"I performed a {scan_depth} scan for '{username}' but found no active public profiles, Sir."
        
        report = [f"Intelligence Briefing for handle: '{username}'", f"Scan Depth: {scan_depth}\n"]
        report.extend(results)
        
        return "\n".join(report)

    except Exception as e:
        logger.error(f"Maigret scan failed: {e}")
        return f"I encountered a technical issue during the neural reconnaissance: {type(e).__name__}"

@registry.register
async def lookup_email_footprint(email: str) -> str:
    """Identify which major services an email address is registered on.
    
    Use this to understand Sir's digital ecosystem (e.g. identifying which 
    professional or social platforms he utilizes).
    
    email: The email address to verify (e.g. 'sir@stark.industries')
    """
    if not HOLEHE_AVAILABLE:
        return "Email footprint analysis (Holehe) is not installed, Sir."

    try:
        out = []
        modules = holehe_core.import_submodules("holehe.modules")
        
        # This is a bit resource intensive, we run them in parallel
        # Note: Holehe core is synchronous in some parts, we use a wrapper
        for module in modules:
            try:
                # Basic check without triggering resets
                found = await asyncio.to_thread(module.main, email, out)
            except:
                continue

        platforms = [res["name"] for res in out if res["exists"]]
        
        if not platforms:
            return f"I found no public service registrations linked to '{email}', Sir."
            
        return f"Sir's digital footprint includes following verified registrations: {', '.join(platforms)}."

    except Exception as e:
        logger.error(f"Holehe scan failed: {e}")
        return f"Failed to map email footprint: {type(e).__name__}"
