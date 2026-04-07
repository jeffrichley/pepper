"""Integration tests for the full foundation.

Tests concurrent writes and hook lifecycle.
"""

import threading

from pepper.hooks.shared import append_to_daily_log, get_daily_log_path


def test_concurrent_daily_log_writes(temp_vault):
    """Two threads writing to the same daily log should not corrupt it."""
    results = {"errors": []}

    def write_entries(prefix: str, count: int):
        try:
            for i in range(count):
                append_to_daily_log(
                    vault_path=temp_vault,
                    content=f"{prefix} entry {i}",
                    source="session",
                    session_id=f"{prefix}-{i}",
                )
        except Exception as e:
            results["errors"].append(str(e))

    t1 = threading.Thread(target=write_entries, args=("thread1", 10))
    t2 = threading.Thread(target=write_entries, args=("thread2", 10))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results["errors"]) == 0, f"Errors: {results['errors']}"

    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()

    for i in range(10):
        assert f"thread1 entry {i}" in text
        assert f"thread2 entry {i}" in text


def test_filelock_prevents_partial_writes(temp_vault):
    """Verify that filelock ensures atomic appends."""
    barrier = threading.Barrier(2)

    def write_with_barrier(session_id: str):
        barrier.wait()
        append_to_daily_log(
            vault_path=temp_vault,
            content=f"Content from {session_id}",
            source="session",
            session_id=session_id,
        )

    t1 = threading.Thread(target=write_with_barrier, args=("simultaneous-1",))
    t2 = threading.Thread(target=write_with_barrier, args=("simultaneous-2",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()

    assert "(session: simultaneous-1)" in text
    assert "(session: simultaneous-2)" in text
    assert "Content from simultaneous-1" in text
    assert "Content from simultaneous-2" in text
