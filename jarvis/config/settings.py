"""Jarvis configuration management."""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Ollama Cloud configuration for Gemma 4."""
    api_key: str = ""
    host: str = "https://ollama.com"
    model: str = "gemma4:31b-cloud"
    temperature: float = 0.7
    timeout: int = 60


@dataclass
class GeminiConfig:
    """Gemini Flash API configuration for real-time queries."""
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.7


@dataclass
class VoiceConfig:
    """Voice pipeline configuration (Phase 2)."""
    enabled: bool = False
    wake_word: str = "hey stark"
    stt_model: str = "base"
    tts_voice: str = "en_US-lessac-medium"


@dataclass
class DaemonConfig:
    """Daemon and system configuration."""
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "jarvis")
    log_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "jarvis" / "logs")
    db_path: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "jarvis" / "jarvis.db")
    shell_whitelist: list = field(default_factory=lambda: [
        "ls", "cat", "head", "tail", "wc", "grep", "find", "date", "cal",
        "df", "du", "free", "uptime", "whoami", "hostname", "uname",
        "echo", "pwd", "which", "file", "stat", "md5sum", "sha256sum",
    ])
    shell_unrestricted: bool = False


@dataclass
class JarvisConfig:
    """Root configuration for Jarvis."""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    user_title: str = "Sir"
    user_name: str = "Tony Stark"
    user_occupation: str = "Engineer"
    user_interests: str = "Innovation"
    user_context: str = ""

    def __post_init__(self):
        """Ensure directories exist."""
        self.daemon.data_dir.mkdir(parents=True, exist_ok=True)
        self.daemon.log_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> JarvisConfig:
    """Load configuration from environment variables and .env file."""
    # Load .env file if it exists
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        _load_dotenv(env_path)

    config = JarvisConfig(
        ollama=OllamaConfig(
            api_key=os.getenv("OLLAMA_API_KEY", ""),
            host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
            model=os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud"),
        ),
        gemini=GeminiConfig(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        ),
        daemon=DaemonConfig(
            log_level=os.getenv("JARVIS_LOG_LEVEL", "INFO"),
        ),
        user_title=os.getenv("JARVIS_USER_TITLE", "Sir"),
        user_name=os.getenv("JARVIS_USER_NAME", "Tony Stark"),
        user_occupation=os.getenv("JARVIS_USER_OCCUPATION", "Engineer"),
        user_interests=os.getenv("JARVIS_USER_INTERESTS", "Innovation"),
        user_context=os.getenv("JARVIS_USER_CONTEXT", ""),
    )

    # Validate critical config
    if not config.ollama.api_key:
        logger.warning("OLLAMA_API_KEY not set — Gemma 4 brain will not be available")
    if not config.gemini.api_key:
        logger.warning("GEMINI_API_KEY not set — real-time search will not be available")

    return config


def save_config(updates: dict):
    """Save configuration updates back to the .env file."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    current_content = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    current_content[key.strip()] = value.strip().strip("'\"")
    
    # Apply updates
    current_content.update(updates)
    
    # Write back
    with open(env_path, "w") as f:
        f.write("# J.A.R.V.I.S. Configuration\n")
        f.write("# Generated during onboarding interview\n\n")
        for key, value in sorted(current_content.items()):
            f.write(f"{key}={value}\n")
    
    # Also update current environment for immediate use
    for key, value in updates.items():
        os.environ[key] = value


def _load_dotenv(path: Path):
    """Simple .env file loader — no external dependency needed."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key:
                        os.environ[key] = value
    except Exception as e:
        logger.warning(f"Failed to load .env file: {e}")
