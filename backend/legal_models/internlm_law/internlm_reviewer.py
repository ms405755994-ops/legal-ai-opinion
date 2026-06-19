"""
InternLM-Law 备用法律复核模型（V1 mock）
"""
from typing import Dict, List, Optional


def review_with_internlm_law(
    case_detail: str,
    goals: str,
    analysis_markdown: str,
    cases: List[Dict],
) -> Dict:
    """Mock 法律复核，返回风险提示和建议"""
    return {
        "reviewer": "InternLM-Law (mock)",
        "summary": "备用法律复核完成。本分析不构成正式法律意见。",
        "risks": [
            {
                "title": "电子证据认定风险",
                "description": "注意电子证据的真实性、合法性和关联性审查。",
                "severity": "low",
            },
        ],
        "risk_items": [
            {
                "title": "电子证据认定风险",
                "description": "注意电子证据的真实性、合法性和关联性审查。",
                "severity": "low",
            },
        ],
    }
