"""
数据源管理 —— JSON 文件 CRUD
"""

import json
import os
import threading
from typing import List, Optional
from copy import deepcopy

from schemas.models import SourceItem, SourceCreate, SourceUpdate

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sources.json")


class SourceManager:
    """数据源管理器（线程安全单例）"""

    _instance: Optional["SourceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SourceManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._ensure_data_file()

    def _ensure_data_file(self) -> None:
        if not os.path.exists(DATA_FILE):
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def _read(self) -> List[dict]:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: List[dict]) -> None:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── CRUD ───────────────────────────────────────────

    def list_all(self) -> List[SourceItem]:
        """列出所有数据源"""
        with self._lock:
            return [SourceItem(**s) for s in self._read()]

    def list_enabled(self) -> List[SourceItem]:
        """列出所有启用的数据源"""
        with self._lock:
            return [SourceItem(**s) for s in self._read() if s.get("enabled", True)]

    def get(self, source_id: str) -> Optional[SourceItem]:
        with self._lock:
            for s in self._read():
                if s["id"] == source_id:
                    return SourceItem(**s)
        return None

    def create(self, item: SourceCreate) -> SourceItem:
        with self._lock:
            data = self._read()
            # 检查重复
            for s in data:
                if s["id"] == item.id:
                    raise ValueError(f"数据源 ID '{item.id}' 已存在")
            new_item = item.model_dump()
            data.append(new_item)
            self._write(data)
            return SourceItem(**new_item)

    def update(self, source_id: str, update: SourceUpdate) -> Optional[SourceItem]:
        with self._lock:
            data = self._read()
            for i, s in enumerate(data):
                if s["id"] == source_id:
                    upd = update.model_dump(exclude_unset=True)
                    data[i].update(upd)
                    self._write(data)
                    return SourceItem(**data[i])
        return None

    def delete(self, source_id: str) -> bool:
        with self._lock:
            data = self._read()
            new_data = [s for s in data if s["id"] != source_id]
            if len(new_data) == len(data):
                return False
            self._write(new_data)
            return True


def get_source_manager() -> SourceManager:
    return SourceManager()
