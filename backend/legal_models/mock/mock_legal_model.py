"""
Mock 法律模型 —— 用于 V1 本地开发和测试
"""
from typing import Dict, List


def mock_decompose_case(case_detail: str) -> Dict:
    """Mock 案件拆解"""
    return {
        "case_type": "民商事",
        "sub_type": "合同纠纷",
        "key_facts": [case_detail[:200]] if case_detail else [],
        "legal_issues": ["合同效力", "违约责任"],
        "parties": {"plaintiff": "甲方", "defendant": "乙方"},
    }


def mock_search_keywords(case_detail: str, goals: str) -> List[str]:
    """Mock 检索关键词生成"""
    keywords = [
        "合同纠纷 类案检索",
        "违约责任 裁判标准",
        "合同解除 法律适用",
        "损害赔偿 计算方式",
        "合同效力 认定规则",
        "履行抗辩 司法实践",
    ]
    return keywords
