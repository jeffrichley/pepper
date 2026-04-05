"""Tests for pyqmd integration with Pepper vault.

These test that pyqmd is properly configured and can search vault content.
"""

import subprocess
from pathlib import Path

import pytest

VAULT = Path(__file__).parent.parent / "Memory"


@pytest.mark.slow
def test_qmd_index_completes():
    """qmd index vault should complete without error."""
    result = subprocess.run(
        ["uv", "run", "qmd", "index", "vault"],
        capture_output=True,
        text=True,
        cwd=str(VAULT.parent),
    )
    assert result.returncode == 0, f"Index failed: {result.stderr}"


@pytest.mark.slow
def test_qmd_search_returns_results():
    """Searching for known content should return results."""
    subprocess.run(
        ["uv", "run", "qmd", "index", "vault"],
        capture_output=True,
        cwd=str(VAULT.parent),
    )

    result = subprocess.run(
        ["uv", "run", "qmd", "search", "executive assistant", "-c", "vault"],
        capture_output=True,
        text=True,
        cwd=str(VAULT.parent),
    )
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.slow
def test_qmd_search_new_file():
    """A newly created and indexed file should be searchable."""
    test_file = VAULT / "research" / "test_search_file.md"
    try:
        test_file.write_text(
            "# Quantum Entanglement in Robotic Systems\n\n"
            "This is a unique test document about quantum robotics.\n"
        )
        subprocess.run(
            ["uv", "run", "qmd", "index", "vault"],
            capture_output=True,
            cwd=str(VAULT.parent),
        )

        result = subprocess.run(
            ["uv", "run", "qmd", "search", "quantum entanglement robotics", "-c", "vault"],
            capture_output=True,
            text=True,
            cwd=str(VAULT.parent),
        )
        assert "quantum" in result.stdout.lower() or "robotics" in result.stdout.lower()
    finally:
        if test_file.exists():
            test_file.unlink()
