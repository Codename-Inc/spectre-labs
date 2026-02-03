"""
Build manifest parsing for spectre-build.

Parses markdown files with YAML frontmatter to configure build loop runs.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BuildManifest:
    """Configuration for a build loop run, loaded from a manifest file."""

    tasks: str
    context: list[str] = field(default_factory=list)
    max_iterations: int = 10
    agent: str = "claude"
    validate: bool = False

    # Source tracking
    manifest_path: str | None = None


def _parse_yaml_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content.

    Simple parser that handles the subset of YAML we need:
    - key: value (strings, numbers, booleans)
    - key: [list, items] or key:\\n  - item1\\n  - item2

    Args:
        content: Full markdown file content

    Returns:
        Dict of frontmatter key-value pairs, empty if no frontmatter
    """
    # Match YAML frontmatter block
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    yaml_block = match.group(1)
    result: dict = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in yaml_block.split("\n"):
        # Skip empty lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check for list item (indented with -)
        if line.startswith("  - ") or line.startswith("\t- "):
            if current_key and current_list is not None:
                value = line.lstrip().lstrip("-").strip()
                current_list.append(value)
            continue

        # Check for key: value
        if ":" in stripped:
            # Save previous list if any
            if current_key and current_list is not None:
                result[current_key] = current_list

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if not value:
                # Start of a list
                current_key = key
                current_list = []
            elif value.startswith("[") and value.endswith("]"):
                # Inline list: key: [a, b, c]
                items = value[1:-1].split(",")
                result[key] = [item.strip().strip("'\"") for item in items if item.strip()]
                current_key = None
                current_list = None
            else:
                # Simple value
                result[key] = _parse_yaml_value(value)
                current_key = None
                current_list = None

    # Save final list if any
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _parse_yaml_value(value: str) -> str | int | bool:
    """Parse a YAML scalar value."""
    # Strip quotes
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Boolean
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    return value


def load_manifest(path: str) -> BuildManifest:
    """Load and parse a build manifest file.

    Paths in the manifest are resolved relative to the manifest file's directory.

    Args:
        path: Path to the manifest markdown file

    Returns:
        BuildManifest with resolved absolute paths

    Raises:
        FileNotFoundError: If manifest file doesn't exist
        ValueError: If manifest is missing required fields
    """
    manifest_path = Path(path).resolve()

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    content = manifest_path.read_text(encoding="utf-8")
    frontmatter = _parse_yaml_frontmatter(content)

    if not frontmatter:
        raise ValueError(f"No YAML frontmatter found in manifest: {path}")

    if "tasks" not in frontmatter:
        raise ValueError(f"Manifest missing required 'tasks' field: {path}")

    # Resolve paths relative to manifest directory
    manifest_dir = manifest_path.parent

    def resolve_path(p: str) -> str:
        """Resolve a path relative to manifest directory."""
        path_obj = Path(p)
        if path_obj.is_absolute():
            return str(path_obj)
        return str((manifest_dir / path_obj).resolve())

    # Build manifest object
    tasks = resolve_path(str(frontmatter["tasks"]))

    context_raw = frontmatter.get("context", [])
    if isinstance(context_raw, str):
        context_raw = [context_raw]
    context = [resolve_path(str(c)) for c in context_raw]

    return BuildManifest(
        tasks=tasks,
        context=context,
        max_iterations=int(frontmatter.get("max_iterations", 10)),
        agent=str(frontmatter.get("agent", "claude")),
        validate=bool(frontmatter.get("validate", False)),
        manifest_path=str(manifest_path),
    )
