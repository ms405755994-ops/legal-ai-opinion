LEGAL_DISCLAIMER = (
    "本系统仅用于类案检索、法律问题初步分析、案件处理思路整理和文书准备参考，"
    "不构成正式法律意见，不替代执业律师服务。系统输出可能存在遗漏、错误或不适用于"
    "具体案件的情况。正式提交法院、仲裁机构、行政机关或用于重大决策前，请务必由"
    "执业律师进行人工复核。"
)

MOCK_CASE_NOTICE = "注意：以下案例为 MOCK 模拟数据，仅用于系统功能测试，不可作为真实法律依据。"

UNVERIFIED_CASE_NOTICE = (
    "未找到可核验的真实案例链接，因此该观点仅作为一般分析，不作为案例支持观点。"
)

DEEPSEEK_SYSTEM_PROMPT = f"""你是一个法律类案检索与案件处理思路助手，不是律师，不能输出正式法律意见。

硬性规则：
1. 不得编造案例。
2. 不得编造案号。
3. 不得编造法院名称。
4. 不得编造裁判观点。
5. 不得编造案例链接。
6. 不得把模型记忆中的案例当成真实案例使用。
7. 只能使用系统提供的 cases 列表中的案例。
8. 每一个法律处理思路，必须绑定至少一个 cases 列表中的案例。
9. 如果某个观点没有真实案例链接，必须明确写：
   “未找到可核验的真实案例链接，因此该观点仅作为一般分析，不作为案例支持观点。”
10. 如果使用 mock 案例，必须明确写：
   “以下案例为 MOCK 模拟数据，仅用于功能测试，不可作为真实法律依据。”
11. 最终结论必须区分：
   - 案例支持较强
   - 案例支持一般
   - 案例支持不足
   - 高风险主张
12. 不得承诺胜诉。
13. 不得替代律师。
14. 必须建议用户在正式提交材料前让执业律师复核。

法律免责声明：
{LEGAL_DISCLAIMER}
"""


NO_CASE_LINK_NOTICE = (
    "系统未找到可核验类案链接，因此本报告不提供案例支持型结论。"
    "以下仅为法律依据、政策依据和一般处理思路。"
)

REVIEW_NOT_ENABLED_NOTICE = "独立法律复核模型未启用，本报告未经过第二法律模型复核。"

# -- result_type classification --
RESULT_TYPE_CASE = {"case", "guiding_case", "typical_case", "judgment"}
RESULT_TYPE_LEGAL_BASIS = {"judicial_interpretation", "policy", "statute"}
RESULT_TYPE_OTHER = {"article", "unknown"}


def classify_result_type(title: str, snippet: str = "", extracted_text: str = "") -> str:
    combined = f"{title} {snippet} {extracted_text}"
    for kw in ["司法解释", "解释（一", "解释（二", "解释（三", "解释（四", "最高法释", "最高检释", "法释"]:
        if kw in combined:
            return "judicial_interpretation"
    if "指导性案例" in combined:
        return "guiding_case"
    if "典型案例" in combined:
        return "typical_case"
    for kw in ["裁判要旨", "基本案情", "裁判理由", "人民法院", "判决书", "裁定书", "案号"]:
        if kw in combined:
            return "judgment"
    for kw in ["意见", "通知", "办法", "规定", "条例", "实施细则"]:
        if kw in title and not any(ck in combined for ck in ["裁判要旨", "判决书", "案号"]):
            return "policy"
    for kw in ["中华人民共和国", "民法典", "刑法", "劳动法", "劳动合同法", "社会保险法", "住房公积金条例"]:
        if kw in title:
            return "statute"
    return "unknown"


# -- labor dispute detection --
LABOR_DISPUTE_KEYWORDS = [
    "劳动合同", "员工", "辞退", "解除劳动关系", "经济补偿",
    "赔偿金", "工资", "公积金", "社保", "仲裁", "离职", "入职",
    "劳动关系", "劳动报酬", "加班费", "年终奖", "提成", "补缴",
    "协商解除", "违法解除", "解除协议", "补偿款", "离职协议",
    "停工", "停产", "生活费", "劳动仲裁", "用人单位", "经营困难",
    "工资支付", "劳动争议", "仲裁裁决", "仲裁委",
]


def is_labor_dispute(case_detail: str) -> bool:
    score = sum(1 for kw in LABOR_DISPUTE_KEYWORDS if kw in case_detail)
    return score >= 3

REPORT_SECTION_TITLES = [
    "一、重要免责声明",
    "二、案件初步判断",
    "三、用户目标拆解",
    "四、争议焦点",
    "五、检索结果分类摘要",
    "六、类案链接",
    "七、法律依据与政策依据",
    "八、处理思路",
    "九、证据补强清单",
    "十、谈判与仲裁/诉讼路径",
    "十一、主要风险",
    "十二、复核状态",
    "十三、引用链接汇总",
    "十四、下一步行动清单",
]
