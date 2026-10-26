"""应用映射管理：用户文件优先，内置模板仅作首次种子。"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.paths import apps_path, resource_path

logger = logging.getLogger(__name__)


class AppMapping:
    def __init__(
        self,
        user_path: Optional[Path] = None,
        bundled_path: Optional[Path] = None,
    ):
        self._user_path = Path(user_path) if user_path else apps_path()
        self._bundled_path = Path(bundled_path) if bundled_path else resource_path("apps.json")
        self._lock = threading.RLock()
        self._raw: Dict[str, str] = {}
        self._index: Dict[str, str] = {}

    @property
    def user_path(self) -> Path:
        return self._user_path

    def load(self) -> "AppMapping":
        with self._lock:
            data = self._read_file(self._user_path)
            if data is None:
                data = self._read_file(self._bundled_path) or {}
                self._raw = data
                self._rebuild_locked()
                self._write_locked()
            else:
                self._raw = data
                self._rebuild_locked()
        return self

    def _read_file(self, path: Path) -> Optional[Dict[str, str]]:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("根节点必须是 JSON 对象")
            return {str(key): str(value) for key, value in raw.items()}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error("读取应用映射失败 %s: %s", path, exc)
            self._backup_broken_file(path)
            return None

    def _backup_broken_file(self, path: Path) -> None:
        try:
            broken = path.with_name(path.name + ".bad")
            os.replace(path, broken)
            logger.warning("损坏的映射文件已备份为 %s", broken)
        except OSError as exc:
            logger.warning("备份损坏映射文件失败: %s", exc)

    def _write_locked(self) -> bool:
        temp_path = None
        try:
            self._user_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._user_path.with_name(self._user_path.name + ".tmp")
            temp_path.write_text(
                json.dumps(self._raw, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(temp_path, self._user_path)
            return True
        except OSError as exc:
            logger.error("保存应用映射失败: %s", exc)
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            return False

    def _rebuild_locked(self) -> None:
        self._index = {key.lower(): value for key, value in self._raw.items()}

    def save(self) -> bool:
        with self._lock:
            return self._write_locked()

    def lookup(self, exe_name: str) -> str:
        with self._lock:
            return self._index.get(exe_name.lower(), exe_name)

    def items(self) -> List[Tuple[str, str]]:
        with self._lock:
            return list(self._raw.items())

    def has_key(self, exe_name: str) -> bool:
        with self._lock:
            return exe_name.lower() in self._index

    def add(self, exe_name: str, display_name: str) -> bool:
        exe_name = exe_name.strip()
        display_name = display_name.strip()
        if not exe_name or not display_name:
            raise ValueError("可执行文件名和映射名称不能为空")

        def operation() -> None:
            self._remove_case_insensitive_locked(exe_name)
            self._raw[exe_name] = display_name

        return self._mutate(operation)

    def update(self, old_exe: str, new_exe: str, display_name: str) -> bool:
        new_exe = new_exe.strip()
        display_name = display_name.strip()
        if not new_exe or not display_name:
            raise ValueError("可执行文件名和映射名称不能为空")

        def operation() -> None:
            self._raw.pop(old_exe, None)
            self._remove_case_insensitive_locked(new_exe)
            self._raw[new_exe] = display_name

        return self._mutate(operation)

    def remove(self, exe_name: str) -> bool:
        def operation() -> None:
            self._raw.pop(exe_name, None)

        return self._mutate(operation)

    def _remove_case_insensitive_locked(self, exe_name: str) -> None:
        target = exe_name.lower()
        for key in [key for key in self._raw if key.lower() == target]:
            self._raw.pop(key, None)

    def _mutate(self, operation) -> bool:
        with self._lock:
            previous = dict(self._raw)
            operation()
            self._rebuild_locked()
            if self._write_locked():
                return True
            self._raw = previous
            self._rebuild_locked()
            return False
