"""
文件工具 —— JSON 读写
"""
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_locks: Dict[str, Lock] = {}


def _get_lock(path: str) -> Lock:
    if path not in _locks:
        _locks[path] = Lock()
    return _locks[path]


def read_json(filepath: str) -> Optional[Any]:
    """读取 JSON 文件"""
    path = Path(filepath)
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_json(filepath: str, data: Any, indent: int = 2) -> bool:
    """写入 JSON 文件"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(str(path))
    with lock:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except IOError:
            return False
