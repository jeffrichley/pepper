"""Generate the Pepper runtime workspace.

Creates ~/.pepper/ with .claude/ config, CLAUDE.md, .mcp.json,
config.toml, and Memory/ vault scaffold.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader


VAULT_SCAFFOLD_DIRS = [
    "daily/raw",
    "daily/summaries",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "projects",
    "meetings",
    "research",
    "clients",
    "content",
    "team",
    "drafts/active",
    "drafts/sent",
    "tasks",
]

TIER_1_FILES = {
    "IDENTITY.md": (
        "# Identity\n\n"
        "**Name:** Pepper\n"
        "**Emoji:** 🌶️\n"
        "**Role:** Second Brain & Executive Assistant\n"
        "**Created by:** Jeff Richley\n"
    ),
    "SOUL.md": (
        "# Soul\n\n"
        "## Personality\n"
        "[Voice, tone, communication style — customize to your liking]\n\n"
        "## Behavioral Rules\n\n"
        "### Hard Boundaries\n"
        "- NEVER send emails or messages without explicit permission\n"
        "- NEVER access financial data or make purchases\n"
        "- NEVER delete anything without explicit permission\n"
    ),
    "USER.md": (
        "# User Profile\n\n"
        "## About\n"
        "- **Name:** [Your name]\n"
        "- **Timezone:** [Your timezone]\n"
    ),
    "MEMORY.md": (
        "# Memory\n\n"
        "## Active Projects\n\n"
        "## Meeting Decisions\n\n"
        "## Research Notes\n"
    ),
    "OPERATIONS.md": (
        "# Operations\n\n"
        "## Vault\n"
        '- **Location:** Memory/\n'
        '- **Search:** `uv run qmd search vault "query"` for semantic search\n'
    ),
}


def generate_runtime(
    runtime_path: Path | None = None,
    migrate_from: Path | None = None,
) -> Path:
    """Generate the Pepper runtime workspace.

    Args:
        runtime_path: Where to create the workspace. Defaults to ~/.pepper/.
        migrate_from: Path to existing Memory/ vault to copy contents from.

    Returns:
        The runtime path.
    """
    if runtime_path is None:
        runtime_path = Path.home() / ".pepper"

    runtime_path.mkdir(parents=True, exist_ok=True)

    # Load Jinja2 templates
    env = Environment(
        loader=PackageLoader("pepper.init", "templates"),
        keep_trailing_newline=True,
    )

    # --- Generate config files (always overwrite) ---

    # .claude/settings.json
    claude_dir = runtime_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    template = env.get_template("settings.json.j2")
    (claude_dir / "settings.json").write_text(template.render())

    # CLAUDE.md
    template = env.get_template("CLAUDE.md.j2")
    (runtime_path / "CLAUDE.md").write_text(template.render())

    # .mcp.json
    template = env.get_template("mcp.json.j2")
    (runtime_path / ".mcp.json").write_text(template.render())

    # config.toml
    template = env.get_template("config.toml.j2")
    vault_path = str(runtime_path / "Memory")
    (runtime_path / "config.toml").write_text(
        template.render(vault_path=vault_path, runtime_path=str(runtime_path))
    )

    # --- Scaffold vault ---

    vault = runtime_path / "Memory"
    vault.mkdir(exist_ok=True)

    # Migrate BEFORE scaffold so migrated files take precedence over defaults
    if migrate_from and migrate_from.is_dir():
        _migrate_vault(source=migrate_from, dest=vault)

    for dir_path in VAULT_SCAFFOLD_DIRS:
        (vault / dir_path).mkdir(parents=True, exist_ok=True)

    # Only create default Tier 1 files if they don't already exist (from migration or prior init)
    for filename, default_content in TIER_1_FILES.items():
        filepath = vault / filename
        if not filepath.exists():
            filepath.write_text(default_content, encoding="utf-8")

    # --- Install skills from the package ---
    _install_skills(runtime_path)

    return runtime_path


def _install_skills(runtime_path: Path) -> None:
    """Copy skills from the installed package to the runtime .claude/skills/."""
    import shutil

    skills_source = Path(__file__).parent.parent / "skills"
    if not skills_source.is_dir():
        return

    skills_dest = runtime_path / ".claude" / "skills"
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    shutil.copytree(skills_source, skills_dest)


def _migrate_vault(source: Path, dest: Path) -> None:
    """Copy vault contents from source to dest, skipping existing files."""
    import shutil

    for item in source.rglob("*"):
        if item.is_file():
            rel = item.relative_to(source)
            target = dest / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
