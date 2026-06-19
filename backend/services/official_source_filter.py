"""
官方来源过滤 —— 加载和过滤官方在线来源
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ONLINE_SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "online_sources.json"


def load_online_sources() -> List[Dict]:
    """加载官方在线来源列表"""
    if ONLINE_SOURCES_FILE.exists():
        try:
            with open(ONLINE_SOURCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def filter_official_result(results: List[Dict], sources: List[Dict]) -> List[Dict]:
    """过滤只保留来自官方来源的结果"""
    official_domains = set()
    for src in sources:
        if src.get("enabled", True) and src.get("domain"):
            official_domains.add(src["domain"].lower())

    if not official_domains:
        return results

    filtered = []
    for r in results:
        url = r.get("url", r.get("link", ""))
        if any(domain in url.lower() for domain in official_domains):
            filtered.append(r)
    return filtered


def update_online_source(source_id: str, update: Dict[str, Any]) -> Optional[Dict]:
    """更新在线来源配置"""
    sources = load_online_sources()
    for src in sources:
        if src.get("id") == source_id:
            src.update(update)
            with open(ONLINE_SOURCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(sources, f, ensure_ascii=False, indent=2)
            return src
    return None
