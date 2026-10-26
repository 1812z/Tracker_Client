import os
import time

from app.logging_setup import LOG_BASENAME, cleanup_logs


def _make_log(path, age_days):
    path.write_text("test\n", encoding="utf-8")
    timestamp = time.time() - age_days * 86400
    os.utime(path, (timestamp, timestamp))


def test_cleanup_by_age_and_legacy_names(tmp_path):
    current = tmp_path / LOG_BASENAME
    _make_log(current, 100)

    old_backup = tmp_path / f"{LOG_BASENAME}.2026-08-01"
    _make_log(old_backup, 40)

    legacy_backup = tmp_path / "runtime_tracker_2026-07-01.log"
    _make_log(legacy_backup, 60)

    recent_backup = tmp_path / f"{LOG_BASENAME}.2026-10-24"
    _make_log(recent_backup, 2)

    deleted = cleanup_logs(tmp_path, retention_days=30, retention_count=10)

    assert deleted == 2
    assert current.exists()
    assert recent_backup.exists()
    assert not old_backup.exists()
    assert not legacy_backup.exists()


def test_cleanup_by_count_keeps_newest(tmp_path):
    current = tmp_path / LOG_BASENAME
    _make_log(current, 100)

    backups = []
    for index in range(1, 6):
        path = tmp_path / f"{LOG_BASENAME}.2026-10-0{index}"
        _make_log(path, index)
        backups.append(path)

    deleted = cleanup_logs(tmp_path, retention_days=3650, retention_count=2)

    assert deleted == 3
    assert current.exists()
    assert backups[0].exists()
    assert backups[1].exists()
    assert not backups[2].exists()
    assert not backups[3].exists()
    assert not backups[4].exists()


def test_current_log_is_never_deleted(tmp_path):
    current = tmp_path / LOG_BASENAME
    _make_log(current, 400)

    deleted = cleanup_logs(tmp_path, retention_days=1, retention_count=1)

    assert deleted == 0
    assert current.exists()
