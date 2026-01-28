"""Spectre shared utilities module.

Provides common functionality used across CLI modules:
- Agent and command discovery
- Frontmatter parsing
- Output formatting (JSON, JSONL, text/table)
- Configuration management
"""

from cli.shared.discovery import (
    # Debug utilities
    DEBUG,
    debug,
    # Agent discovery
    AgentSource,
    get_agent_sources,
    find_agent,
    list_all_agents,
    load_agent_details,
    load_agent_instructions,
    # Command discovery
    CommandSource,
    get_command_sources,
    find_command,
    list_all_commands,
    load_command_details,
    load_command_prompt,
    validate_command_name,
    interpolate_arguments,
    # Shared utilities
    parse_frontmatter,
    strip_frontmatter,
    get_project_root,
    load_installed_plugins,
)

from cli.shared.output import (
    # JSON output
    format_json,
    output_json,
    # JSONL streaming output
    format_jsonl_line,
    output_jsonl,
    stream_jsonl,
    # Table output
    format_table,
    output_table,
    # Path display
    truncate_path,
    format_path_display,
    # Output selection
    get_output_handler,
    # Error output
    output_error,
    output_warning,
)

from cli.shared.config import (
    # Path utilities
    get_spectre_home,
    get_claude_home,
    get_codex_home,
    get_config_path,
    get_plugins_dir,
    get_agents_dir,
    get_commands_dir,
    get_skills_dir,
    # Config class
    SpectreConfig,
    # Config loading
    load_config_file,
    load_config,
    get_config,
    reset_config,
    # Environment overrides
    get_env_overrides,
)

__all__ = [
    # Debug utilities
    "DEBUG",
    "debug",
    # Agent discovery
    "AgentSource",
    "get_agent_sources",
    "find_agent",
    "list_all_agents",
    "load_agent_details",
    "load_agent_instructions",
    # Command discovery
    "CommandSource",
    "get_command_sources",
    "find_command",
    "list_all_commands",
    "load_command_details",
    "load_command_prompt",
    "validate_command_name",
    "interpolate_arguments",
    # Shared utilities
    "parse_frontmatter",
    "strip_frontmatter",
    "get_project_root",
    "load_installed_plugins",
    # Output formatting
    "format_json",
    "output_json",
    "format_jsonl_line",
    "output_jsonl",
    "stream_jsonl",
    "format_table",
    "output_table",
    "truncate_path",
    "format_path_display",
    "get_output_handler",
    "output_error",
    "output_warning",
    # Configuration
    "get_spectre_home",
    "get_claude_home",
    "get_codex_home",
    "get_config_path",
    "get_plugins_dir",
    "get_agents_dir",
    "get_commands_dir",
    "get_skills_dir",
    "SpectreConfig",
    "load_config_file",
    "load_config",
    "get_config",
    "reset_config",
    "get_env_overrides",
]
