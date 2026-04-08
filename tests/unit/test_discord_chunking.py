"""Tests for paragraph-aware message chunking."""

from pepper.integrations.discord.chunking import smart_chunk


def test_short_message_no_split():
    """Messages under the limit are returned as-is."""
    # Arrange
    text = "Hello, world!"

    # Act
    result = smart_chunk(text, limit=2000)

    # Assert
    assert result == ["Hello, world!"]


def test_split_at_paragraph():
    """Splits at double newline when possible."""
    # Arrange
    para1 = "A" * 40
    para2 = "B" * 40
    text = f"{para1}\n\n{para2}"

    # Act
    result = smart_chunk(text, limit=50)

    # Assert
    assert len(result) == 2
    assert result[0] == para1
    assert result[1] == para2


def test_split_at_newline():
    """Falls back to single newline when no paragraph break fits."""
    # Arrange
    line1 = "A" * 40
    line2 = "B" * 40
    text = f"{line1}\n{line2}"

    # Act
    result = smart_chunk(text, limit=50)

    # Assert
    assert len(result) == 2
    assert result[0] == line1
    assert result[1] == line2


def test_split_at_space():
    """Falls back to space when no newline fits."""
    # Arrange
    text = "word " * 20  # 100 chars
    text = text.strip()

    # Act
    result = smart_chunk(text, limit=30)

    # Assert — all chunks should be within limit
    for chunk in result:
        assert len(chunk) <= 30
    assert " ".join(result) == text


def test_hard_cut_no_boundaries():
    """Hard cuts when no natural boundary exists."""
    # Arrange
    text = "A" * 100

    # Act
    result = smart_chunk(text, limit=30)

    # Assert
    assert len(result) == 4  # 30+30+30+10
    assert all(len(c) <= 30 for c in result)
    assert "".join(result) == text


def test_no_chunk_exceeds_limit():
    """No chunk exceeds the Discord limit regardless of input."""
    # Arrange — a mix of paragraphs, lines, and long words
    text = (
        "Short paragraph.\n\n"
        + "A" * 1500
        + "\n\n"
        + "Another paragraph with some words.\n"
        + "B" * 500
    )

    # Act
    result = smart_chunk(text, limit=2000)

    # Assert
    for chunk in result:
        assert len(chunk) <= 2000


def test_preserves_content():
    """All original content is preserved across chunks."""
    # Arrange
    text = "Hello\n\nWorld\n\nThis is a test\n\nOf chunking"

    # Act
    result = smart_chunk(text, limit=20)

    # Assert — recombined content matches original (minus whitespace changes)
    recombined = "\n".join(result)
    for word in ["Hello", "World", "This", "is", "a", "test", "Of", "chunking"]:
        assert word in recombined
