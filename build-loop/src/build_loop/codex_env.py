"""
Codex credential sync for sandboxed execution.

Copies Codex credentials from user home to workspace-local directory
so subprocesses can authenticate when running in sandbox mode.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory for Codex credential sync (relative to workspace root)
CODEX_SUBAGENT_DIR = ".spectre/codex-subagent"


def _safe_copy_file(src: Path, dst: Path) -> bool:
    """Safely copy a file, rejecting symlinks to prevent symlink attacks."""
    if src.is_symlink():
        logger.debug("Skipping symlink: %s", src)
        return False
    if not src.is_file():
        return False
    try:
        shutil.copy2(src, dst)
        return True
    except (OSError, shutil.Error) as e:
        logger.debug("Failed to copy %s: %s", src, e)
        return False


def setup_codex_home() -> Path:
    """Sync Codex credentials to workspace for sandboxed execution.

    Copies config.toml and auth.json from ~/.codex to .spectre/codex-subagent/
    so child processes can authenticate while running in sandbox mode.

    Returns the absolute path to the workspace CODEX_HOME directory.
    """
    workspace_home = Path.cwd() / CODEX_SUBAGENT_DIR
    workspace_home.mkdir(parents=True, exist_ok=True)

    user_codex_home = Path.home() / ".codex"

    config_src = user_codex_home / "config.toml"
    if _safe_copy_file(config_src, workspace_home / "config.toml"):
        logger.debug("Synced config.toml to %s", workspace_home)

    auth_src = user_codex_home / "auth.json"
    if _safe_copy_file(auth_src, workspace_home / "auth.json"):
        logger.debug("Synced auth.json to %s", workspace_home)

    return workspace_home.resolve()
