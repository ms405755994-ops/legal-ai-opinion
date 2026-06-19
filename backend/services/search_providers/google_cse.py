"""
Google Custom Search Engine (CSE) API Provider
"""
import httpx
from typing import Dict, List


def search_google_cse(query: str, api_key: str, cx: str, max_results: int = 10) -> List[Dict]:
    """通过 Google CSE API 搜索"""
    if not api_key or not cx:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": min(max_results, 10)}

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "source": "google_cse",
        })
    return results[:max_results]
