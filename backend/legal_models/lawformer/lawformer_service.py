"""
Lawformer 类案相似度排序模型（V1 mock）
"""
from typing import Dict, List


def rank_cases_with_lawformer(
    case_detail: str,
    goals: str,
    candidate_cases: List[Dict],
) -> List[Dict]:
    """Mock 类案相似度排序"""
    ranked = []
    for i, case in enumerate(candidate_cases):
        ranked.append({
            **case,
            "lawformer_score": round(1.0 - i * 0.1, 2) if i < 10 else 0.5,
            "lawformer_rank": i + 1,
        })
    return ranked
