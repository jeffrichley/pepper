"""Tests for pepper init — runtime workspace generation."""

import json

from pepper.init.generator import generate_runtime


def test_generate_creates_directory_structure(tmp_path):
    """Pepper init creates the expected directory structure."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    assert (runtime / ".claude").is_dir()
    assert (runtime / ".claude" / "settings.json").is_file()
    assert (runtime / "CLAUDE.md").is_file()
    assert (runtime / ".mcp.json").is_file()
    assert (runtime / "config.toml").is_file()
    assert (runtime / "Memory").is_dir()


def test_generate_creates_vault_scaffold(tmp_path):
    """Pepper init creates empty Tier 1 files and directory structure."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    vault = runtime / "Memory"
    assert (vault / "IDENTITY.md").is_file()
    assert (vault / "SOUL.md").is_file()
    assert (vault / "USER.md").is_file()
    assert (vault / "MEMORY.md").is_file()
    assert (vault / "OPERATIONS.md").is_file()
    assert (vault / "daily" / "raw").is_dir()
    assert (vault / "daily" / "summaries").is_dir()
    assert (vault / "weekly").is_dir()
    assert (vault / "projects").is_dir()


def test_generate_settings_has_hooks(tmp_path):
    """Generated settings.json references installed hook entry points."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    settings = json.loads((runtime / ".claude" / "settings.json").read_text())
    hook_cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "pepper.hooks.session_start_context" in hook_cmd


def test_generate_mcp_has_channel(tmp_path):
    """Generated .mcp.json references pepper-channel entry point."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    mcp = json.loads((runtime / ".mcp.json").read_text())
    assert mcp["mcpServers"]["pepper-channel"]["command"] == "uv"
    assert "pepper-channel" in mcp["mcpServers"]["pepper-channel"]["args"]


def test_generate_does_not_overwrite_existing_vault(tmp_path):
    """Pepper init preserves existing vault files."""
    runtime = tmp_path / ".pepper"
    vault = runtime / "Memory"
    vault.mkdir(parents=True)
    (vault / "IDENTITY.md").write_text("# My Custom Identity")

    generate_runtime(runtime_path=runtime)

    assert (vault / "IDENTITY.md").read_text() == "# My Custom Identity"


def test_generate_overwrites_config_files(tmp_path):
    """Pepper init regenerates config files even if they exist."""
    runtime = tmp_path / ".pepper"
    runtime.mkdir(parents=True)
    (runtime / "CLAUDE.md").write_text("old content")

    generate_runtime(runtime_path=runtime)

    assert "Pepper" in (runtime / "CLAUDE.md").read_text()


def test_migrate_copies_vault_contents(tmp_path):
    """Pepper init --migrate copies existing vault to runtime."""
    source_vault = tmp_path / "repo" / "Memory"
    source_vault.mkdir(parents=True)
    (source_vault / "IDENTITY.md").write_text("# My Real Identity")
    daily_raw = source_vault / "daily" / "raw"
    daily_raw.mkdir(parents=True)
    (daily_raw / "2026-04-06.md").write_text("# Today's log")

    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime, migrate_from=source_vault)

    assert (runtime / "Memory" / "IDENTITY.md").read_text() == "# My Real Identity"
    assert (
        runtime / "Memory" / "daily" / "raw" / "2026-04-06.md"
    ).read_text() == "# Today's log"


def test_generate_installs_skills(tmp_path):
    """Pepper init copies skills into runtime .claude/skills/."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    skills_dir = runtime / ".claude" / "skills"
    assert skills_dir.is_dir()
    assert (skills_dir / "coding" / "SKILL.md").is_file()
    assert (skills_dir / "google" / "SKILL.md").is_file()


def test_migrate_does_not_overwrite_existing_runtime_vault(tmp_path):
    """Migration skips files that already exist in the runtime vault."""
    source_vault = tmp_path / "repo" / "Memory"
    source_vault.mkdir(parents=True)
    (source_vault / "IDENTITY.md").write_text("# Source Identity")

    runtime = tmp_path / ".pepper"
    vault = runtime / "Memory"
    vault.mkdir(parents=True)
    (vault / "IDENTITY.md").write_text("# Existing Identity")

    generate_runtime(runtime_path=runtime, migrate_from=source_vault)

    assert (vault / "IDENTITY.md").read_text() == "# Existing Identity"
