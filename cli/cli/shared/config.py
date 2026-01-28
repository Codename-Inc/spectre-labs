"""Configuration management for Spectre CLI.

Provides configuration loading from files and environment variables:
- Default paths and settings
- YAML config file loading (~/.spectre/config.yaml)
- Environment variable overrides (SPECTRE_*)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# Default Paths
# =============================================================================


def get_spectre_home() -> Path:
    """Get the Spectre home directory.

    Checks SPECTRE_HOME environment variable, falls back to ~/.spectre.
    """
    env_home = os.environ.get("SPECTRE_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".spectre"


def get_claude_home() -> Path:
    """Get the Claude Code home directory.

    Checks CLAUDE_HOME environment variable, falls back to ~/.claude.
    """
    env_home = os.environ.get("CLAUDE_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".claude"


def get_codex_home() -> Path:
    """Get the Codex home directory.

    Checks CODEX_HOME environment variable, falls back to ~/.codex.
    """
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".codex"


def get_config_path() -> Path:
    """Get the path to the Spectre config file."""
    return get_spectre_home() / "config.yaml"


def get_plugins_dir() -> Path:
    """Get the plugins installation directory."""
    return get_claude_home() / "plugins"


def get_agents_dir() -> Path:
    """Get the user agents directory."""
    return get_claude_home() / "agents"


def get_commands_dir() -> Path:
    """Get the user commands directory."""
    return get_claude_home() / "commands"


def get_skills_dir() -> Path:
    """Get the skills installation directory.

    For Claude Code, this is ~/.claude/skills/.
    For Codex, this is ~/.codex/skills/.
    Returns Claude Code path by default.
    """
    return get_claude_home() / "skills"


# =============================================================================
# Configuration Dataclass
# =============================================================================


@dataclass
class SpectreConfig:
    """Configuration settings for Spectre CLI.

    Attributes:
        spectre_home: Base directory for Spectre data
        claude_home: Claude Code home directory
        codex_home: Codex home directory
        debug: Enable debug output
        default_output_format: Default output format (text, json, jsonl)
        sandbox_mode: Default sandbox mode for subagent execution
        extra: Additional config values from file
    """

    spectre_home: Path = field(default_factory=get_spectre_home)
    claude_home: Path = field(default_factory=get_claude_home)
    codex_home: Path = field(default_factory=get_codex_home)
    debug: bool = False
    default_output_format: str = "text"
    sandbox_mode: str = "workspace-write"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def plugins_dir(self) -> Path:
        """Get plugins directory."""
        return self.claude_home / "plugins"

    @property
    def agents_dir(self) -> Path:
        """Get user agents directory."""
        return self.claude_home / "agents"

    @property
    def commands_dir(self) -> Path:
        """Get user commands directory."""
        return self.claude_home / "commands"

    @property
    def skills_dir(self) -> Path:
        """Get skills directory."""
        return self.claude_home / "skills"

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self.spectre_home / "config.yaml"


# =============================================================================
# Config File Loading
# =============================================================================


def parse_yaml_simple(content: str) -> dict[str, Any]:
    """Parse simple YAML (key: value pairs only).

    This is a minimal YAML parser using only stdlib. Supports:
    - String values (with or without quotes)
    - Boolean values (true/false/yes/no)
    - Numeric values (int, float)
    - Comments (lines starting with #)

    Does NOT support:
    - Nested structures
    - Lists
    - Multi-line values

    For complex YAML, the full PyYAML library should be used.
    """
    result: dict[str, Any] = {}

    for line in content.split("\n"):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Parse key: value
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        # Remove inline comments
        if "#" in value:
            # Only remove if # is not inside quotes
            if not (value.startswith('"') or value.startswith("'")):
                value = value.split("#")[0].strip()

        # Parse value type
        result[key] = _parse_yaml_value(value)

    return result


def _parse_yaml_value(value: str) -> Any:
    """Parse a YAML value string to appropriate Python type."""
    if not value:
        return None

    # Remove quotes
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    # Boolean
    lower_value = value.lower()
    if lower_value in ("true", "yes", "on"):
        return True
    if lower_value in ("false", "no", "off"):
        return False
    if lower_value in ("null", "none", "~"):
        return None

    # Numeric
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # String (unquoted)
    return value


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        path: Config file path (default: ~/.spectre/config.yaml)

    Returns:
        Dict of config values, empty dict if file doesn't exist
    """
    if path is None:
        path = get_config_path()

    if not path.is_file():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
        return parse_yaml_simple(content)
    except (OSError, ValueError):
        return {}


# =============================================================================
# Environment Variable Overrides
# =============================================================================


def get_env_overrides() -> dict[str, Any]:
    """Get configuration overrides from environment variables.

    Supported environment variables:
    - SPECTRE_HOME: Base Spectre directory
    - SPECTRE_DEBUG: Enable debug mode (1, true, yes)
    - SPECTRE_OUTPUT_FORMAT: Default output format
    - SPECTRE_SANDBOX_MODE: Default sandbox mode
    - CLAUDE_HOME: Claude Code home directory
    - CODEX_HOME: Codex home directory
    """
    overrides: dict[str, Any] = {}

    # Path overrides
    if "SPECTRE_HOME" in os.environ:
        overrides["spectre_home"] = Path(os.environ["SPECTRE_HOME"]).expanduser()
    if "CLAUDE_HOME" in os.environ:
        overrides["claude_home"] = Path(os.environ["CLAUDE_HOME"]).expanduser()
    if "CODEX_HOME" in os.environ:
        overrides["codex_home"] = Path(os.environ["CODEX_HOME"]).expanduser()

    # Boolean overrides
    debug_env = os.environ.get("SPECTRE_DEBUG", "").lower()
    if debug_env in ("1", "true", "yes", "on"):
        overrides["debug"] = True
    elif debug_env in ("0", "false", "no", "off"):
        overrides["debug"] = False

    # String overrides
    if "SPECTRE_OUTPUT_FORMAT" in os.environ:
        overrides["default_output_format"] = os.environ["SPECTRE_OUTPUT_FORMAT"]
    if "SPECTRE_SANDBOX_MODE" in os.environ:
        overrides["sandbox_mode"] = os.environ["SPECTRE_SANDBOX_MODE"]

    return overrides


# =============================================================================
# Main Config Loading
# =============================================================================


def load_config(config_path: Path | None = None) -> SpectreConfig:
    """Load Spectre configuration.

    Loads configuration from:
    1. Default values
    2. Config file (~/.spectre/config.yaml)
    3. Environment variables (highest priority)

    Args:
        config_path: Override config file path

    Returns:
        SpectreConfig instance with merged settings
    """
    # Start with defaults
    config = SpectreConfig()

    # Load from file
    file_config = load_config_file(config_path)
    if file_config:
        if "debug" in file_config:
            config.debug = bool(file_config["debug"])
        if "output_format" in file_config:
            config.default_output_format = str(file_config["output_format"])
        if "sandbox_mode" in file_config:
            config.sandbox_mode = str(file_config["sandbox_mode"])
        # Store any extra config values
        known_keys = {"debug", "output_format", "sandbox_mode"}
        config.extra = {k: v for k, v in file_config.items() if k not in known_keys}

    # Apply environment overrides
    env_overrides = get_env_overrides()
    if "spectre_home" in env_overrides:
        config.spectre_home = env_overrides["spectre_home"]
    if "claude_home" in env_overrides:
        config.claude_home = env_overrides["claude_home"]
    if "codex_home" in env_overrides:
        config.codex_home = env_overrides["codex_home"]
    if "debug" in env_overrides:
        config.debug = env_overrides["debug"]
    if "default_output_format" in env_overrides:
        config.default_output_format = env_overrides["default_output_format"]
    if "sandbox_mode" in env_overrides:
        config.sandbox_mode = env_overrides["sandbox_mode"]

    return config


# =============================================================================
# Singleton Config Access
# =============================================================================

_config: SpectreConfig | None = None


def get_config() -> SpectreConfig:
    """Get the global configuration instance.

    Lazy-loads configuration on first access.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (mainly for testing)."""
    global _config
    _config = None
