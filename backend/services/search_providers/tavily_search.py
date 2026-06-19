"""
Tavily Search API Provider（推荐）
"""
import httpx
from typing import Dict, List, Optional


def search_tavily(query: str, api_key: str, max_results: int = 10,
                  include_domains: Optional[List[str]] = None) -> List[Dict]:
    """通过 Tavily Search API 搜索"""
    if not api_key:
        return []

    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": min(max_results, 20),
    }
    if include_domains:
        payload["include_domains"] = include_domains

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", item.get("snippet", "")),
            "source": "tavily",
        })
    return results[:max_results]
