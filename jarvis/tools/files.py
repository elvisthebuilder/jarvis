"""File operations — search, open, and basic file management."""

import subprocess
import logging
from pathlib import Path

from .registry import registry

logger = logging.getLogger(__name__)


@registry.register
def open_file(filepath: str) -> str:
    """Open a file with its default application.
    
    filepath: Path to the file to open
    """
    path = Path(filepath).expanduser()
    
    if not path.exists():
        return f"File not found: {filepath}"
    
    result = subprocess.run(
        ["xdg-open", str(path)],
        capture_output=True, text=True, timeout=10,
    )
    
    if result.returncode == 0:
        return f"Opened {path.name}."
    return f"Failed to open file: {result.stderr.strip()}"


@registry.register
def open_folder(folderpath: str = "") -> str:
    """Open a folder in the file manager.
    
    folderpath: Path to the folder to open (defaults to home directory)
    """
    path = Path(folderpath).expanduser() if folderpath else Path.home()
    
    if not path.exists():
        return f"Folder not found: {folderpath}"
    
    result = subprocess.run(
        ["xdg-open", str(path)],
        capture_output=True, text=True, timeout=10,
    )
    
    if result.returncode == 0:
        return f"Opened {path.name or 'home'} in file manager."
    return f"Failed to open folder: {result.stderr.strip()}"


@registry.register
def find_files(name: str, directory: str = "") -> str:
    """Search for files by name in a directory.
    
    name: File name or pattern to search for (e.g., '*.pdf', 'report')
    directory: Directory to search in (defaults to home directory)
    """
    search_dir = Path(directory).expanduser() if directory else Path.home()
    
    if not search_dir.exists():
        return f"Directory not found: {directory}"
    
    result = subprocess.run(
        ["find", str(search_dir), "-maxdepth", "4",
         "-iname", f"*{name}*", "-type", "f",
         "-not", "-path", "*/.*"],
        capture_output=True, text=True, timeout=15,
    )
    
    if result.returncode == 0 and result.stdout.strip():
        files = result.stdout.strip().split("\n")[:15]  # Limit results
        file_list = "\n".join(f"  - {f}" for f in files)
        count = len(files)
        return f"Found {count} file(s) matching '{name}':\n{file_list}"
    
    return f"No files matching '{name}' found in {search_dir}."
