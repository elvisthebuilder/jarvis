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
    
    # Increased depth and precision for Jarvis
    result = subprocess.run(
        ["find", str(search_dir), "-maxdepth", "6",
         "-iname", f"*{name}*", "-type", "f",
         "-not", "-path", "*/.*"],
        capture_output=True, text=True, timeout=15,
    )
    
    if result.returncode == 0 and result.stdout.strip():
        files = result.stdout.strip().split("\n")[:15]
        file_list = "\n".join(f"  - {f}" for f in files)
        return f"Found {len(files)} file(s) matching '{name}':\n{file_list}"
    
    return f"No files matching '{name}' found."


@registry.register
def read_file(filepath: str) -> str:
    """Read the contents of a file.
    
    filepath: Path to the file to read
    """
    path = Path(filepath).expanduser()
    if not path.exists():
        return f"Error: File {filepath} does not exist."
    if not path.is_file():
        return f"Error: {filepath} is not a file."
        
    try:
        # Limit read to 10k characters for safety
        content = path.read_text(encoding='utf-8')
        if len(content) > 10000:
            return content[:10000] + "\n... [Content Truncated]"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@registry.register
def write_file(filepath: str, content: str) -> str:
    """Write or overwrite content to a file.
    
    filepath: Path to the file to write
    content: The text content to write
    """
    path = Path(filepath).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return f"Successfully wrote to {filepath}."
    except Exception as e:
        return f"Error writing file: {str(e)}"


@registry.register
def list_directory(directory: str = "") -> str:
    """List the contents of a directory.
    
    directory: Path to the directory (defaults to home)
    """
    path = Path(directory).expanduser() if directory else Path.home()
    if not path.exists() or not path.is_dir():
        return f"Error: Directory {directory} not found."
        
    try:
        items = list(path.iterdir())
        files = [f.name for f in items if f.is_file()]
        dirs = [d.name + "/" for d in items if d.is_dir()]
        
        output = []
        if dirs: output.append(f"Directories: {', '.join(sorted(dirs)[:20])}")
        if files: output.append(f"Files: {', '.join(sorted(files)[:30])}")
        
        return "\n".join(output) if output else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {str(e)}"
