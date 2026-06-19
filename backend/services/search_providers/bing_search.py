"""
Bing Custom Search API Provider
"""
import httpx
from typing import Dict, List, Optional


def search_bing(query: str, api_key: str, custom_config_id: str, endpoint: str = "",
                max_results: int = 10) -> List[Dict]:
    """通过 Bing Custom Search API 搜索"""
    if not api_key or not custom_config_id:
        return []

    url = endpoint or "https://api.bing.microsoft.com/v7.0/custom/search"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "customconfig": custom_config_id, "count": min(max_results, 50)}

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("webPages", {}).get("value", []):
        results.append({
            "title": item.get("name", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
            "source": "bing",
        })
    return results[:max_results]
