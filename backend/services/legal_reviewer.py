import os
from typing import Dict, List

from legal_models.disc_lawllm.disc_reviewer import review_with_disc_lawllm
from legal_models.internlm_law.internlm_reviewer import review_with_internlm_law


def review_legal_analysis(case_detail: str, goals, analysis_markdown: str, cases: List[Dict]) -> Dict:
    use_disc = os.getenv("USE_DISC_LAWLLM", "false").lower() == "true"
    use_internlm = os.getenv("USE_INTERNLM_LAW", "false").lower() == "true"

    if use_disc:
        return review_with_disc_lawllm(case_detail, goals, analysis_markdown, cases)
    if use_internlm:
        return review_with_internlm_law(case_detail, goals, analysis_markdown, cases)

    return {
        "legal_relation_check": "当前为 MOCK 复核，未进行真实法律模型复核，不能判断法律关系和案由是否准确。",
        "case_usage_check": "当前未进行真实法律模型复核；MOCK 案例只能作为系统测试案例，不能作为真实法律依据。",
        "missing_issues": [
            "诉讼时效或仲裁时效是否存在风险",
            "解除、赔偿等请求是否已有明确通知或催告",
            "关键事实是否有直接证据支撑（书证、电子数据、证人证言等）",
        ],
        "risk_warnings": [
            "不能承诺胜诉或承诺全部诉求被支持。",
            "模拟案例不可作为真实法律依据。",
            "正式提交前应替换为可核验真实案例并由执业律师复核。",
        ],
        "overclaim_risks": [
            "避免将一般法律分析写成确定裁判结论。",
            "避免使用未经核验的案号、法院、链接。",
        ],
        "final_review_level": "需要人工复核",
        "reviewer": "mock",
    }
