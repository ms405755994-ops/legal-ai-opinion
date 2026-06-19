"""
案例链接存储 —— 管理自动检索到的案例链接
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "case_links.json"
_lock = Lock()


class CaseLinkStore:
    def __init__(self):
        self._links: List[Dict] = []
        self._load()

    def _load(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self._links = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._links = []

    def _save(self):
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._links, f, ensure_ascii=False, indent=2)

    def list_links(self) -> List[Dict]:
        return list(self._links)

    def update_link(self, link_id: str, update: Dict) -> Optional[Dict]:
        with _lock:
            for link in self._links:
                if link.get("id") == link_id:
                    link.update(update)
                    self._save()
                    return link
        return None

    def delete_link(self, link_id: str) -> bool:
        with _lock:
            before = len(self._links)
            self._links = [l for l in self._links if l.get("id") != link_id]
            if len(self._links) < before:
                self._save()
                return True
        return False

    def add_link(self, link: Dict) -> Dict:
        with _lock:
            if "id" not in link:
                import uuid
                link["id"] = str(uuid.uuid4())[:8]
            self._links.append(link)
            self._save()
        return link


_store: Optional[CaseLinkStore] = None


def get_case_link_store() -> CaseLinkStore:
    global _store
    if _store is None:
        _store = CaseLinkStore()
    return _store
