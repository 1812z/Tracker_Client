"""日志初始化：按天轮转，并按配置清理历史日志。"""

import logging
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import List, Optional, Tuple

LOG_BASENAME = "runtime_tracker.log"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LEGACY_PREFIX = "runtime_tracker_"
LEGACY_SUFFIX = ".log"


def _is_backup_file(path: Path) -> bool:
    name = path.name
    if name == LOG_BASENAME:
        return False
    if name.startswith(LOG_BASENAME + "."):
        return True
    # 兼容旧版本 runtime_tracker_YYYY-MM-DD.log 的命名。
    return name.startswith(LEGACY_PREFIX) and name.endswith(LEGACY_SUFFIX)


def cleanup_logs(log_dir: Path, retention_days: int, retention_count: int) -> int:
    """删除超过保留天数或数量的历史日志，返回删除数量。"""
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return 0

    try:
        days = max(0, int(retention_days))
        count = max(0, int(retention_count))
    except (TypeError, ValueError):
        return 0
    if days == 0 and count == 0:
        return 0

    now = time.time()
    kept: List[Tuple[float, Path]] = []
    deleted = 0

    for path in log_dir.iterdir():
        try:
            if not path.is_file() or not _is_backup_file(path):
                continue
            mtime = path.stat().st_mtime
        except OSError:
            continue

        if days > 0 and now - mtime > days * 86400:
            try:
                path.unlink()
                deleted += 1
                continue
            except OSError:
                pass

        kept.append((mtime, path))

    if count > 0:
        kept.sort(key=lambda item: item[0], reverse=True)
        for _, path in kept[count:]:
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass

    return deleted


def apply_log_retention(log_dir: Path, retention_days: int, retention_count: int) -> int:
    """更新当前轮转 handler 的数量上限，并立即清理历史日志。"""
    count = max(1, int(retention_count))
    for handler in logging.getLogger().handlers:
        if isinstance(handler, TimedRotatingFileHandler):
            handler.backupCount = count
    return cleanup_logs(log_dir, retention_days, count)


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    retention_days: int = 30,
    retention_count: int = 30,
    cleanup: bool = True,
) -> logging.Logger:
    log_dir = Path(log_dir)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler: Optional[TimedRotatingFileHandler] = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            str(log_dir / LOG_BASENAME),
            when="midnight",
            backupCount=max(1, int(retention_count)),
            encoding="utf-8",
            delay=True,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        print(f"初始化日志文件失败，仅输出到控制台: {exc}")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if cleanup:
        try:
            cleanup_logs(log_dir, retention_days, retention_count)
        except Exception:
            pass

    return logging.getLogger("runtime_tracker")
