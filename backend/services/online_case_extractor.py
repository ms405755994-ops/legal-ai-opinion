"""
在线案例提取 —— 从搜索 API 结果中提取案例信息
"""
from typing import Dict, List


def extract_online_case(search_result: Dict) -> Dict:
    """从单个搜索结果提取案例信息"""
    return {
        "title": search_result.get("title", ""),
        "url": search_result.get("url", search_result.get("link", "")),
        "snippet": search_result.get("snippet", search_result.get("content", "")),
        "source": search_result.get("source", ""),
        "result_type": "unknown",
        "useful": False,
        "useful_score": 0.0,
        "verified": False,
        "auto_collected": True,
        "can_be_used_as_formal_citation": False,
    }
