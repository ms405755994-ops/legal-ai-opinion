"""
DISC-LawLLM 法律复核模型（V1 mock）
"""
from typing import Dict, List, Optional


def review_with_disc_lawllm(
    case_detail: str,
    goals: str,
    analysis_markdown: str,
    cases: List[Dict],
) -> Dict:
    """Mock 法律复核，返回风险提示和建议"""
    return {
        "reviewer": "DISC-LawLLM (mock)",
        "summary": "本分析基于 AI 类案检索结果，以下为参考性风险提示。",
        "risks": [
            {
                "title": "类案参考局限性",
                "description": "在线检索到的案例可能不具代表性，需人工核实案例的时效性和关联性。",
                "severity": "medium",
            },
            {
                "title": "区域法律差异",
                "description": "不同地区的司法实践可能存在差异，本案需结合当地法院裁判倾向。",
                "severity": "medium",
            },
        ],
        "risk_items": [
            {
                "title": "类案参考局限性",
                "description": "在线检索到的案例可能不具代表性，需人工核实案例的时效性和关联性。",
                "severity": "medium",
            },
            {
                "title": "区域法律差异",
                "description": "不同地区的司法实践可能存在差异，本案需结合当地法院裁判倾向。",
                "severity": "medium",
            },
        ],
    }
