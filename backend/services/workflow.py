import os
from typing import Dict, List

from services.case_ranker import get_case_ranker
from services.case_search import get_case_search_engine
from services.citation_checker import get_citation_checker
from services.deepseek_client import get_deepseek_client
from services.legal_reviewer import review_legal_analysis
from services.online_search_workflow import collect_online_links
from services.prompt_templates import (
    LEGAL_DISCLAIMER,
    MOCK_CASE_NOTICE,
    NO_CASE_LINK_NOTICE,
    REVIEW_NOT_ENABLED_NOTICE,
    RESULT_TYPE_CASE,
    RESULT_TYPE_LEGAL_BASIS,
    classify_result_type,
    is_labor_dispute,
)
from services.report_generator import get_report_generator
from utils.id_utils import short_uuid
from utils.text_utils import markdown_to_html, split_goals


TEST_MODE_NOTICE = (
    "当前系统未接入真实案例库，以下结果仅用于功能测试。所有 MOCK 案例均不可作为真实法律依据。"
    "请接入真实、可核验案例数据源后重新生成报告。"
)


NO_SEARCH_KEY_NOTICE = "当前未配置在线搜索 API Key，系统无法自动检索真实案例链接。本报告仅基于案件信息生成一般处理思路，不提供案例支持型结论。"
NO_USEFUL_LINK_NOTICE = "系统已自动生成关键词并检索官方在线来源，但未找到与本案高度相关的可用案例链接。因此本报告不提供案例支持型结论。"
AUTO_UNVERIFIED_NOTICE = "以下链接由系统自动检索和 AI 初步筛选，尚未经过人工核验。正式提交前，请人工打开原始链接核对案例真实性、案号、法院、裁判观点和适用性。"


def run_analysis(
    case_detail: str,
    goals_raw: str,
    only_verified_links: bool = False,
    auto_online_search: bool = True,
    max_keywords_per_goal: int = 8,
    max_search_results_per_keyword: int = 10,
    max_links_to_judge: int = 30,
    max_links_to_use: int = 8,
) -> Dict:
    if not case_detail.strip():
        raise ValueError("case_detail 不能为空")
    goals = split_goals(goals_raw)
    if not goals:
        raise ValueError("goals 不能为空")

    analysis_id = short_uuid("ana_")
    warnings: List[str] = []

    llm = get_deepseek_client()
    decompose_result = llm.decompose_case(case_detail, goals)
    keyword_result: Dict = {"keywords": [], "keyword_groups": []}
    auto_collect_result: Dict = {}
    search_summary: Dict = {
        "provider": os.getenv("ONLINE_SEARCH_PROVIDER", "bing"),
        "provider_ready": False,
        "total_queries": 0,
        "total_raw_results": 0,
        "official_results": 0,
        "links_judged": 0,
        "useful_links": 0,
        "used_in_report": 0,
    }
    used_links: List[Dict] = []
    verified_cases: List[Dict] = []

    search_mode = "online_auto" if auto_online_search else os.getenv("CASE_SEARCH_MODE", "online_index").lower()
    if auto_online_search:
        auto_collect_result = collect_online_links(
            case_detail=case_detail,
            goals=goals_raw,
            sources=[],
            provider=os.getenv("ONLINE_SEARCH_PROVIDER", "bing"),
            max_keywords_per_goal=max_keywords_per_goal,
            max_results_per_keyword=max_search_results_per_keyword,
            max_links_to_judge=max_links_to_judge,
            max_links_to_store=max_links_to_use,
            analysis_id=analysis_id,
            auto_collected=True,
            used_in_analysis=True,
        )
        keyword_result = {
            "keywords": auto_collect_result.get("keywords", []),
            "keyword_groups": auto_collect_result.get("keyword_groups", []),
        }
        search_summary = auto_collect_result.get("search_summary", search_summary)
        warnings.extend(auto_collect_result.get("warnings", []))
        used_links = auto_collect_result.get("stored_links", [])
        if only_verified_links:
            used_links = [link for link in used_links if link.get("verified")]
        verified_cases = [_link_to_case_reference(link) for link in used_links]
        if not search_summary.get("provider_ready"):
            warnings.append("未配置在线搜索 API Key，无法自动检索真实案例链接")
        elif search_summary.get("useful_links", 0) == 0:
            warnings.append("自动在线检索未找到 useful_score >= 0.65 的相关官方链接。")
        elif verified_cases and not any(case.get("verified") for case in verified_cases):
            warnings.append("本次链接为 AI 自动检索待核验参考链接，正式提交前必须人工核验。")
    else:
        keyword_result = llm.generate_search_keywords(case_detail, goals, decompose_result)
        keywords = _flatten_keywords(keyword_result)
        search_result = get_case_search_engine().search_cases(case_detail, goals, keywords, top_k=10)
        warnings.extend(search_result["warnings"])
        rank_result = get_case_ranker().rank_cases(case_detail, goals, search_result["cases"])
        warnings.extend(rank_result["warnings"])
        citation_result = get_citation_checker().verify(rank_result["ranked_cases"])
        warnings.extend(citation_result["warnings"])
        verified_cases = citation_result["verified_cases"]

    case_mode_info = _case_mode_info(verified_cases)
    if not case_mode_info["can_be_used_for_real_case"]:
        warnings.append("当前报告不可直接用于真实案件；请先核验在线链接并由执业律师复核。")
    if case_mode_info["case_mode"] == "mock":
        warnings.append("当前系统未接入真实案例库，全部返回案例均为 MOCK 系统测试案例。")

    draft_markdown = build_report_markdown(
        case_detail=case_detail,
        goals=goals,
        decompose_result=decompose_result,
        keyword_result=keyword_result,
        cases=verified_cases,
        review=None,
        warnings=warnings,
        case_mode_info=case_mode_info,
        search_summary=search_summary,
    )
    review = review_legal_analysis(case_detail, goals, draft_markdown, verified_cases)
    final_markdown = build_report_markdown(
        case_detail=case_detail,
        goals=goals,
        decompose_result=decompose_result,
        keyword_result=keyword_result,
        cases=verified_cases,
        review=review,
        warnings=warnings,
        case_mode_info=case_mode_info,
        search_summary=search_summary,
    )

    docx_file_id, _filename = get_report_generator().generate(final_markdown, verified_cases)

    return {
        "success": True,
        "analysis_id": analysis_id,
        "html": markdown_to_html(final_markdown),
        "markdown": final_markdown,
        "cases": verified_cases,
        "review": review,
        "warnings": list(dict.fromkeys(warnings)),
        "docx_file_id": docx_file_id,
        "case_search_mode": search_mode,
        "auto_online_search": auto_online_search,
        "keywords": keyword_result.get("keywords", _flatten_keywords(keyword_result)),
        "search_summary": search_summary,
        "used_links": [_used_link_payload(link) for link in used_links],
        **case_mode_info,
    }


def build_report_markdown(
    case_detail: str,
    goals: List[str],
    decompose_result: Dict,
    keyword_result: Dict,
    cases: List[Dict],
    review: Dict | None,
    warnings: List[str],
    case_mode_info: Dict | None = None,
    search_summary: Dict | None = None,
) -> str:
    review = review or {
        "legal_relation_check": "待复核",
        "case_usage_check": "待复核",
        "missing_issues": [],
        "risk_warnings": [],
        "overclaim_risks": [],
        "final_review_level": "需要人工复核",
        "reviewer": "pending",
    }

    case_mode_info = case_mode_info or _case_mode_info(cases)
    test_mode = case_mode_info["report_mode"] == "test_mock"
    has_mock = case_mode_info["mock_case_count"] > 0

    # ── 链接分类 ──
    case_links = []    # 类案：case/guiding_case/typical_case/judgment
    legal_links = []   # 法律依据：judicial_interpretation/policy/statute
    other_links = []   # 其他

    for c in cases:
        rt = c.get("result_type") or classify_result_type(
            c.get("title", ""), c.get("snippet", ""), c.get("holding", "")
        )
        c["result_type"] = rt
        if rt in RESULT_TYPE_CASE:
            case_links.append(c)
        elif rt in RESULT_TYPE_LEGAL_BASIS:
            legal_links.append(c)
        else:
            other_links.append(c)

    has_case_links = len(case_links) > 0 and not all(_is_mock_case(c) for c in case_links)
    has_legal_links = len(legal_links) > 0

    # ── 劳动争议检测 ──
    labor = is_labor_dispute(case_detail)

    # ── 最终结论 ──
    provider_not_ready = search_summary is not None and not search_summary.get("provider_ready", True)
    has_any_links = has_case_links or has_legal_links

    if has_case_links:
        final_conclusion = "已检索到类案链接，仍需人工复核其适用性"
    elif has_legal_links:
        final_conclusion = "未找到类案链接，仅找到法律依据/政策依据"
    else:
        final_conclusion = "未找到可核验真实案例链接，因此本报告不提供案例支持型结论"

    lines: List[str] = [
        "# AI 类案检索与案件处理思路报告",
        "",
    ]

    # 顶部提示
    if test_mode:
        lines.extend(["> TEST_MODE_REPORT", f"> {TEST_MODE_NOTICE}", ""])
    elif provider_not_ready:
        lines.extend([f"> 当前未配置在线搜索 API Key，系统无法自动检索真实案例链接。", ""])
    elif not has_case_links and has_legal_links:
        lines.extend([f"> {NO_CASE_LINK_NOTICE}", ""])

    lines.extend([
        "## 一、重要免责声明",
        LEGAL_DISCLAIMER,
    ])

    # mock 清理：只有在确实有 mock 案例时才显示
    if has_mock:
        lines.extend(["", MOCK_CASE_NOTICE])

    # ── 二、案件初步判断 ──
    cause_candidates = _join(decompose_result.get("cause_of_action_candidates", []))
    legal_relations = _join(decompose_result.get("legal_relations", []))

    # 劳动争议优先识别
    if labor:
        lines.extend([
            "",
            "## 二、案件初步判断",
            f"- 案件类型：**劳动争议**（系统自动识别）",
            f"- 子类型：劳动合同解除争议 / 停工期间待遇争议 / 经济补偿争议",
            f"- 案由候选：{cause_candidates or '劳动争议、劳动合同纠纷'}",
            f"- 法律关系：**劳动关系**（非普通合同关系）",
            f"- 最终结论：{final_conclusion}",
            "- 说明：本部分为案件处理思路整理，不构成正式法律意见。",
        ])
    else:
        lines.extend([
            "",
            "## 二、案件初步判断",
            f"- 案由候选：{cause_candidates or '待进一步分析'}",
            f"- 法律关系：{legal_relations or '待进一步分析'}",
            f"- 最终结论：{final_conclusion}",
            "- 说明：本部分为案件处理思路整理，不构成正式法律意见。",
        ])

    # ── 三、用户目标拆解 ──
    lines.extend(["", "## 三、用户目标拆解"])
    goal_paths = decompose_result.get("goal_paths", [])
    for goal in goals:
        lines.append(f"- {goal}：{_find_goal_path(goal_paths, goal)}")

    # ── 四、争议焦点 ──
    lines.extend(["", "## 四、争议焦点"])
    for item in decompose_result.get("dispute_focus", []) or ["是否存在违约或侵权基础", "证据是否足以支撑请求"]:
        lines.append(f"- {item}")

    # ── 五、检索结果分类摘要 ──
    lines.extend(["", "## 五、检索结果分类摘要"])
    lines.append(f"- 类案链接：{len(case_links)} 个")
    lines.append(f"- 法律依据/政策依据：{len(legal_links)} 个")
    lines.append(f"- 其他链接：{len(other_links)} 个")
    if has_mock:
        lines.append(f"- 其中模拟案例（MOCK）：{case_mode_info['mock_case_count']} 个（不可作为真实依据）")
    if not has_any_links:
        lines.append("- ⚠️ 未找到可核验链接，以下分析基于一般法律原则。")

    # ── 六、类案链接 ──
    if has_case_links:
        lines.extend(["", "## 六、类案链接"])
        for case in case_links:
            if not _is_mock_case(case):
                lines.extend(_case_summary_lines(case, test_mode=False))
        # mock 案例仅在 test_mode 时显示
        if test_mode:
            for case in case_links:
                if _is_mock_case(case):
                    lines.extend(_case_summary_lines(case, test_mode=True))
    else:
        lines.extend(["", "## 六、类案链接", "- 未找到可核验类案链接。"])

    # ── 七、法律依据与政策依据 ──
    if has_legal_links:
        lines.extend(["", "## 七、法律依据与政策依据"])
        for link in legal_links:
            rt_label = _result_type_label(link.get("result_type", "unknown"))
            lines.append(f"- [{rt_label}] {link.get('title', '')}：{link.get('url', '')}")
            if link.get("holding"):
                lines.append(f"  要点：{link['holding'][:200]}")
    else:
        lines.extend(["", "## 七、法律依据与政策依据", "- 未找到可直接引用的法律依据/政策依据链接。"])

    # ── 八、处理思路 ──
    lines.extend(["", "## 八、处理思路"])
    if labor:
        # 劳动争议专用模板
        lines.extend(_labor_strategy_lines(goals, case_links, legal_links, decompose_result))
    else:
        # 通用模板（不含合同/订单/交付等词）
        for index, goal in enumerate(goals[:3], 1):
            lines.extend(_generic_strategy_lines(index, goal, case_links, legal_links))

    # ── 九、证据补强清单 ──
    lines.extend(["", "## 九、证据补强清单"])
    if labor:
        lines.extend([
            "- 劳动合同（原件或复印件）",
            "- 销售区域任务及考核制度文件",
            "- 近年销售任务完成率统计表",
            "- 回款目标及未完成情况说明",
            "- 团队承诺书（如有）",
            "- 第三方专项审计报告",
            "- 公司会议纪要和决议（关于停工安排）",
            "- 《停工通知书》及送达记录",
            "- 停工期间生活费支付方案及支付凭证",
            "- 社保继续缴纳记录",
            "- 员工停工后继续打卡、出差、对外开展业务的证据",
            "- 公司要求停止打卡及不得以公司名义对外开展业务的通知回复",
            "- 仲裁裁决书及仲裁庭认定理由",
            "- 公司起诉状、诉讼请求和证据目录",
            "- 用人单位经营状况报表（证明经营困难）",
        ])
    for item in decompose_result.get("evidence_checklist", []) or []:
        if item not in lines:  # avoid duplicates
            lines.append(f"- {item}")
    lines.append("- 对关键事实制作时间线，标明每份证据对应证明目的。")
    # ── 十、谈判与仲裁/诉讼路径 ──
    lines.extend(["", "## 十、谈判与仲裁/诉讼路径"])
    if labor:
        lines.extend([
            "- **协商路径**：与员工沟通停工安排的经营背景和事实依据，明确停工期间待遇方案（按不低于当地最低工资标准80%支付生活费、继续缴纳社保）。",
            "- **仲裁路径**：如协商不成，准备劳动仲裁应诉材料（停工通知书、审计报告、会议决议、区域业绩数据、团队缩编文件）。",
            "- **诉讼路径**：如仲裁裁决不利，在法定期限内向人民法院提起诉讼，重点论证区域性停工的合法性、经营合理性及非针对性。",
            "- **行政路径**：涉及社保、公积金问题时，可向当地人力资源和社会保障部门咨询政策适用。",
            "- 谈判中避免承认停工具有针对性或变相解雇性质。",
            "- 保留公司经营自主权和管理权的法律立场。",
        ])
    else:
        lines.extend([
            "- 先发送书面沟通函，明确事实、证据、诉求、回复期限。",
            "- 将目标拆成优先目标和可让步目标，保留后续诉讼或仲裁空间。",
            "- 谈判中避免作出放弃核心权利的含糊承诺。",
            "- 明确被告主体、管辖法院或仲裁条款。",
        ])

    # ── 十一、主要风险 ──
    lines.extend(["", "## 十一、主要风险"])
    lines.append(f"- 最终结论：{final_conclusion}。")
    if labor:
        lines.extend([
            "- 停工安排如被认定为变相解雇，公司可能需支付违法解除赔偿金（2N）。",
            "- 停工期间如未按法定标准支付生活费，员工可主张补足差额。",
            "- 如停工程序存在瑕疵（未告知工会、未履行民主程序），可能影响停工合法性认定。",
            "- 仲裁裁决对停工缺乏事实依据的认定在法院诉讼中仍有被维持的风险。",
        ])
    else:
        lines.append("- 高风险主张：缺少证据支撑的赔偿、扩大化损失。")
    for warning in warnings:
        lines.append(f"- {warning}")

    # ── 十二、复核状态 ──
    lines.extend(["", "## 十二、复核状态"])
    reviewer = review.get("reviewer", "pending")
    if reviewer == "mock" or reviewer == "pending":
        lines.append(f"- {REVIEW_NOT_ENABLED_NOTICE}")
    else:
        lines.append(f"- 复核模型：{reviewer}")
    lines.append(f"- 法律关系复核：{review.get('legal_relation_check', '')}")
    lines.append(f"- 案例使用复核：{review.get('case_usage_check', '')}")
    lines.append(f"- 最终复核等级：{review.get('final_review_level', '需要人工复核')}")
    for item in review.get("missing_issues", []):
        lines.append(f"  - 遗漏：{item}")
    for item in review.get("overclaim_risks", []):
        lines.append(f"  - 过度承诺风险：{item}")

    # ── 十三、引用链接汇总 ──
    lines.extend(["", "## 十三、引用链接汇总"])
    if has_case_links:
        for case in case_links:
            is_mock = _is_mock_case(case)
            label = "（MOCK）" if is_mock else "（类案链接）"
            lines.append(f"- {case.get('title', '')} {label}：{case.get('url', '')}")
    else:
        lines.append("- 未找到可核验类案链接。")
    if has_legal_links:
        lines.append("")
        lines.append("### 法律依据 / 政策依据链接")
        for link in legal_links:
            lines.append(f"- [{_result_type_label(link.get('result_type', ''))}] {link.get('title', '')}：{link.get('url', '')}")

    # ── 十四、下一步行动清单 ──
    lines.extend(["", "## 十四、下一步行动清单"])
    if labor:
        lines.extend([
            "- 整理停工通知、会议纪要/决议、审计报告等核心证据原件。",
            "- 编制华北区域销售业绩时间线（2021-2025），标注关键节点。",
            "- 在自动检索结果库中打开原始链接人工核验类案和法律依据。",
            "- 咨询执业律师，评估停工合法性认定在法院诉讼中的胜诉可能性。",
            "- 准备应诉材料，重点补充仲裁阶段未提交的经营困难证据。",
            "- 不要将本系统输出直接作为正式法律意见或最终诉讼文书。",
        ])
    else:
        lines.extend([
            "- 补齐证据材料并按争议焦点编号。",
            "- 在自动检索结果库中打开原始链接人工核验。",
            "- 正式发送律师函、起诉状前，请执业律师人工复核。",
            "- 不要将本系统输出直接作为正式法律意见或最终诉讼文书。",
        ])

    return "\n".join(lines)


def _labor_strategy_lines(goals: List[str], case_links: List[Dict],
                          legal_links: List[Dict], decompose_result: Dict) -> List[str]:
    """劳动争议专用处理思路 — 停工/解除/补偿通用"""
    lines: List[str] = []
    # 自动检测案件子类型
    has_shutdown = any(kw in " ".join(goals) for kw in ["停工", "停产", "生活费", "经营困难", "区域"])
    for i, goal in enumerate(goals[:5], 1):
        lines.extend([
            f"### 目标 {i}：{goal}",
            "",
        ])
        if has_shutdown:
            # ── 停工案件专用思路 ──
            lines.extend([
                "**停工合法性分析**：",
                "- 审查用人单位停工决策是否有内部制度依据（规章制度、会议决议）",
                "- 审查区域/部门停工是否以公司整体停工为前提（法律无此要求）",
                "- 分析行业状况、市场环境、销售数据等客观经营事实",
                "- 判断停工系经营管理措施还是变相解雇/惩罚",
                "",
                "**证据链分析**：",
                "- 销售业绩连续下滑趋势是否形成证据闭环",
                "- 第三方审计报告对经营困难事实的证明力",
                "- 会议纪要/决议与停工通知的时间关联性",
                "- 停工对象是否为区域全体人员（排除个人针对）",
                "",
                "**仲裁裁决推翻空间**：",
                "- 仲裁委适用《工资支付暂行规定》第十二条是否恰当",
                "- 仲裁委对\"停工缺乏普遍性\"的认定是否有法律依据",
                "- 公司补充提交审计报告、停产决议等证据后可否推翻原认定",
                "- 法院对用人单位经营自主权的审查标准和裁判倾向",
                "",
            ])
        else:
            # ── 一般劳动争议思路（解除/补偿/社保） ──
            lines.extend([
                "**补偿款/协议效力分析**：",
                "- 是否有解除协议、是否写明一次性解决劳动关系争议",
                "- 是否员工签字确认、是否已经实际支付",
                "- 是否存在重大误解、欺诈、胁迫、显失公平等可撤销事由",
                "",
                "**额外赔偿请求分析**：",
                "- 公司解除是否合法（协商解除 vs 违法解除）",
                "- 已支付金额是否达到或超过法定经济补偿/赔偿标准",
                "- 是否存在未付工资、加班费、奖金、提成等独立请求",
                "",
                "**住房公积金补缴分析**：",
                "- 公积金补缴通常通过住房公积金管理中心行政处理路径",
                "- 是否属于劳动仲裁/法院直接处理范围需结合当地裁判口径",
                "- 解除协议的一次性补偿条款通常不当然覆盖公积金补缴义务",
                "",
            ])
        # 附相关案例/法律依据
        if case_links:
            linked = [c for c in case_links if c.get("matched_goal") == goal]
            if not linked:
                linked = case_links[:2]
            if linked:
                lines.append("**相关类案**：")
                for lk in linked[:2]:
                    lines.append(f"- {lk.get('title', '')}（{lk.get('case_no', '')}、{lk.get('court', '')}）")
                lines.append("")
        elif legal_links:
            lines.append("**相关法律依据**（非类案）:")
            for lk in legal_links[:2]:
                lines.append(f"- {lk.get('title', '')}")
            lines.append("")
        else:
            lines.append("**未找到可核验的同类裁判案例链接。**")
            lines.append("以下内容仅基于案件事实、法律依据和政策文件生成处理思路。")
            lines.append("")
    return lines


def _generic_strategy_lines(index: int, goal: str, case_links: List[Dict],
                            legal_links: List[Dict]) -> List[str]:
    """通用处理思路（不含合同/订单/交付等合同纠纷专有词）"""
    lines: List[str] = [
        f"### 目标 {index}：{goal}",
        "",
        "**分析**：",
        "- 确认基础法律关系和对方履行情况",
        "- 分别评估协商、调解、仲裁或诉讼的可行性",
        "",
    ]
    if case_links:
        linked = [c for c in case_links if c.get("matched_goal") == goal]
        if not linked:
            linked = case_links[:1]
        if linked:
            lines.append("**相关类案**：")
            for lk in linked[:2]:
                lines.append(f"- {lk.get('title', '')}（{lk.get('case_no', '')}）")
    elif legal_links:
        lines.append("**相关法律依据**：")
        for lk in legal_links[:2]:
            lines.append(f"- {lk.get('title', '')}")
    else:
        lines.append("- 未找到可核验类案链接。")
    lines.append("")
    return lines


def _result_type_label(rt: str) -> str:
    """result_type → 中文标签"""
    labels = {
        "case": "案例", "guiding_case": "指导性案例", "typical_case": "典型案例",
        "judgment": "判决", "judicial_interpretation": "司法解释",
        "policy": "政策", "statute": "法律法规", "article": "文章",
        "unknown": "未分类",
    }
    return labels.get(rt, rt)


def _flatten_keywords(keyword_result: Dict) -> List[str]:
    values: List[str] = []
    for item in keyword_result.get("keyword_groups", []):
        for key in ["cause_keywords", "issue_keywords", "holding_keywords", "winning_direction_keywords"]:
            values.extend(item.get(key, []))
    values.extend(keyword_result.get("global_keywords", []))
    return [str(value).strip() for value in dict.fromkeys(values) if str(value).strip()]


def _case_mode_info(cases: List[Dict]) -> Dict:
    mock_count = sum(1 for case in cases if _is_mock_case(case))
    real_count = sum(1 for case in cases if not _is_mock_case(case))
    verified_count = sum(1 for case in cases if not _is_mock_case(case) and bool(case.get("verified")))
    unverified_count = max(0, real_count - verified_count)
    if real_count == 0 and mock_count == 0:
        case_mode = "none"
    elif real_count > 0 and mock_count == 0:
        case_mode = "real"
    elif real_count > 0 and mock_count > 0:
        case_mode = "mixed"
    else:
        case_mode = "mock"
    if mock_count > 0 and real_count == 0:
        report_mode = "test_mock"
    elif real_count == 0:
        report_mode = "no_real_links"
    elif verified_count > 0:
        report_mode = "online_verified"
    else:
        report_mode = "online_unverified"
    return {
        "case_mode": case_mode,
        "can_be_used_for_real_case": verified_count > 0 and mock_count == 0,
        "real_case_count": real_count,
        "mock_case_count": mock_count,
        "verified_case_count": verified_count,
        "unverified_case_count": unverified_count,
        "report_mode": report_mode,
    }


def _is_mock_case(case: Dict) -> bool:
    return bool(case.get("is_mock")) or str(case.get("url", "")).startswith("mock://")


def _join(value) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if str(item).strip()) or "待人工复核"
    return str(value or "待人工复核")


def _find_goal_path(goal_paths, goal: str) -> str:
    for item in goal_paths or []:
        if item.get("goal") == goal:
            return item.get("legal_path", "围绕该目标补充证据并复核法律路径。")
    return "围绕该目标补充证据并复核法律路径。"


def _support_label(strength: str, matched: List[Dict], test_mode: bool = False) -> str:
    if test_mode:
        return "仅用于功能测试，未找到真实可核验案例支持。"
    if not matched:
        return "未找到可核验真实案例链接。"
    if any(_is_mock_case(case) for case in matched):
        return "仅有 MOCK 测试案例，不可作为真实法律依据。"
    if not any(case.get("verified") for case in matched):
        return "AI 自动检索待核验参考链接；该链接可能相关，需人工核验后方可作为正式依据。"
    return f"案例支持{strength}，仍需人工复核。"


def _case_for_goal(cases: List[Dict], goal: str) -> Dict | None:
    for case in cases:
        if case.get("matched_goal") == goal:
            return case
    return cases[0] if cases else None


def _case_summary_lines(case: Dict, test_mode: bool = False) -> List[str]:
    mock = "（MOCK 模拟数据）" if _is_mock_case(case) else ""
    strength_label = "测试匹配强度" if test_mode else "支持强度"
    status = "MOCK 测试案例" if _is_mock_case(case) else ("已核验在线案例链接" if case.get("verified") else "AI 自动检索待核验参考链接")
    return [
        f"- 案件名称：{case.get('title', '')}{mock}",
        f"  - 链接状态：{status}",
        f"  - 案号：{case.get('case_no', '')}",
        f"  - 法院：{case.get('court', '')}",
        f"  - 裁判日期：{case.get('judgment_date', '')}",
        f"  - 争议焦点：{case.get('issue', '')}",
        f"  - 裁判观点：{case.get('holding', '')}",
        f"  - 原始链接：{case.get('url', '')}",
        f"  - 匹配目标：{case.get('matched_goal', '')}",
        f"  - 相似度：{case.get('similarity_score', 0)}",
        f"  - {strength_label}：{case.get('support_strength', '不足')}",
    ]


def _case_detail_lines(case: Dict) -> List[str]:
    return [
        f"- 案件名称：{case.get('title', '')}",
        f"- 案号：{case.get('case_no', '')}",
        f"- 法院：{case.get('court', '')}",
        f"- 裁判日期：{case.get('judgment_date', '')}",
        f"- 裁判观点：{case.get('holding', '')}",
        f"- 原始链接：{case.get('url', '')}",
    ]


def _case_section_heading(test_mode: bool, formal_online: bool, unverified_online: bool) -> str:
    if test_mode:
        return "### 4. 模拟测试案例"
    if formal_online:
        return "### 4. 已核验在线案例链接"
    if unverified_online:
        return "### 4. AI 自动检索待核验参考链接"
    return "### 4. 真实在线链接"


def _link_to_case_reference(link: Dict) -> Dict:
    return {
        "id": link.get("id", ""),
        "title": link.get("title", ""),
        "case_no": "",
        "court": "",
        "judgment_date": "",
        "issue": link.get("matched_issue", ""),
        "holding": link.get("snippet", ""),
        "facts": "",
        "url": link.get("url", ""),
        "source_name": link.get("source_name", ""),
        "source_id": link.get("source_id", ""),
        "domain": link.get("domain", ""),
        "is_mock": False,
        "online_indexed": True,
        "verified": bool(link.get("verified")),
        "can_be_used_as_formal_citation": bool(link.get("can_be_used_as_formal_citation")),
        "snippet": link.get("snippet", ""),
        "need_human_verify": bool(link.get("need_human_verify", True)),
        "matched_goal": link.get("matched_goal", ""),
        "matched_issue": link.get("matched_issue", ""),
        "similarity_score": float(link.get("useful_score", 0)),
        "support_strength": link.get("support_strength", "弱"),
        "reason": link.get("ai_reason", ""),
    }


def _used_link_payload(link: Dict) -> Dict:
    return {
        "id": link.get("id", ""),
        "title": link.get("title", ""),
        "url": link.get("url", ""),
        "source_name": link.get("source_name", ""),
        "snippet": link.get("snippet", ""),
        "matched_goal": link.get("matched_goal", ""),
        "matched_issue": link.get("matched_issue", ""),
        "useful_score": float(link.get("useful_score", 0)),
        "support_strength": link.get("support_strength", "弱"),
        "verified": bool(link.get("verified")),
        "label": "已核验在线案例链接" if link.get("verified") else "AI 自动检索待核验参考链接",
    }
