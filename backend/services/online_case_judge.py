from typing import Dict, List
import concurrent.futures
import time

from config import (
    LINK_JUDGE_BATCH_SIZE, LINK_JUDGE_TIMEOUT_SECONDS, LINK_JUDGE_TOTAL_TIMEOUT_SECONDS,
    AI_FAILURE_MODE, AI_LINK_JUDGE_REQUIRED, ENABLE_RULE_LINK_JUDGE_FALLBACK,
)
from services.deepseek_client import get_deepseek_client
from utils.text_utils import keyword_tokens, overlap_score, split_goals


def _is_strict_link_judge() -> bool:
    """严格模式：AI 必须判断，不允许规则 fallback"""
    return AI_FAILURE_MODE == "strict" and AI_LINK_JUDGE_REQUIRED and not ENABLE_RULE_LINK_JUDGE_FALLBACK


def _allow_heuristic_fallback() -> bool:
    """允许启发式回退：仅在显式 degraded + fallback 开启时"""
    return AI_FAILURE_MODE == "degraded" and ENABLE_RULE_LINK_JUDGE_FALLBACK


def _strict_timeout_judgment(link: Dict, reason: str = "") -> Dict:
    """strict 模式下超时/异常的标记：不参与报告引用"""
    return {
        "useful": False,
        "useful_score": 0.0,
        "result_type": "unknown",
        "can_support_case_argument": False,
        "can_be_legal_basis": False,
        "matched_goal": "",
        "reason": reason or "AI 判断超时（strict 模式，未启用启发式判断）",
        "risk": "未经过 AI 判断，不可作为正式引用依据",
        "need_human_verify": True,
        "excluded_from_report": True,
        "judge_timed_out": True,
    }


def judge_online_links(
    case_detail: str, goals_raw: str, links: List[Dict], max_links: int,
    tracker=None,
) -> Dict:
    """逐条判断（保留兼容），推荐使用 batch_judge_links"""
    judged = []
    warnings: List[str] = []
    goals = split_goals(goals_raw) if isinstance(goals_raw, str) else list(goals_raw)
    for item in links[:max_links]:
        judgment = judge_online_link(case_detail, goals, item)
        judged.append({**item, **judgment})
    return {"judged_links": judged, "warnings": warnings}


def batch_judge_links(
    case_detail: str, goals_raw: str, links: List[Dict], max_links: int,
    tracker=None,
) -> Dict:
    """
    批量判断链接 — 按 LINK_JUDGE_BATCH_SIZE 分批调用 DeepSeek，每批带超时。

    返回: { judged_links, warnings, batches_total, batches_done }
    """
    goals = split_goals(goals_raw) if isinstance(goals_raw, str) else list(goals_raw)
    limit = min(len(links), max_links)
    batch_size = LINK_JUDGE_BATCH_SIZE
    batches = [links[i:i + batch_size] for i in range(0, limit, batch_size)]
    batches_total = len(batches)

    judged: List[Dict] = []
    warnings: List[str] = []
    batches_done = 0
    start_time = time.time()

    if tracker:
        tracker.log(f"开始批量 AI 判断：{limit} 条链接，每批 {batch_size} 条，共 {batches_total} 批",
                    "info")
        tracker.metric("batches_total", batches_total)

    for batch_idx, batch in enumerate(batches):
        batch_num = batch_idx + 1

        # ── 总超时保护 ──
        total_elapsed = time.time() - start_time
        if total_elapsed > LINK_JUDGE_TOTAL_TIMEOUT_SECONDS:
            timeout_reason = f"链接判断阶段超过总超时时间（>{LINK_JUDGE_TOTAL_TIMEOUT_SECONDS}s）"
            warnings.append(f"{timeout_reason}，已停止。已判断 {batches_done}/{batches_total} 批。")
            for remaining_batch in batches[batch_idx:]:
                for link in remaining_batch:
                    if _is_strict_link_judge():
                        judged.append({**link, **_strict_timeout_judgment(link, timeout_reason),
                                       "stage_timeout": True})
                    else:
                        judged.append({**link, **_judge_heuristic(case_detail, goals, link),
                                       "judge_timed_out": True, "stage_timeout": True})
            if tracker:
                mode_label = "strict 模式：AI 判断链接超时，未启用启发式判断。" if _is_strict_link_judge() \
                    else "degraded 模式：AI 判断链接超时，已启用启发式辅助判断。"
                tracker.log(
                    f"链接判断阶段超时：总耗时 {total_elapsed:.0f}s > {LINK_JUDGE_TOTAL_TIMEOUT_SECONDS}s，"
                    f"已完成 {batches_done}/{batches_total} 批。{mode_label}",
                    "warning" if _is_strict_link_judge() else "info"
                )
                tracker.metric("link_judge_stage_timeout", True)
            break

        if tracker:
            tracker.log(f"正在判断第 {batch_num}/{batches_total} 批（{len(batch)} 条链接）", "info")
            tracker.metric("batches_done", batches_done)
            tracker.metric("current_batch", batch_num)

        batch_start = time.time()

        # 批量调用 DeepSeek（带超时）
        batch_results = _batch_judge_with_timeout(case_detail, goals, batch, batch_num)

        if batch_results is None:
            # 超时或异常
            timeout_reason = f"第 {batch_num} 批链接判断超时（>{LINK_JUDGE_TIMEOUT_SECONDS}s）"
            warnings.append(timeout_reason)
            for link in batch:
                if _is_strict_link_judge():
                    judged.append({**link, **_strict_timeout_judgment(link, timeout_reason),
                                   "judge_timed_out": True})
                elif _allow_heuristic_fallback():
                    judged.append({**link, **_judge_heuristic(case_detail, goals, link),
                                   "judge_timed_out": True})
                else:
                    # 非 strict 也非 degraded fallback：标记为需人工核验
                    judged.append({**link, **_strict_timeout_judgment(link, timeout_reason),
                                   "judge_timed_out": True})
            if tracker:
                mode_label = "strict 模式：AI 判断链接超时，未启用启发式判断。" if _is_strict_link_judge() \
                    else ("degraded 模式：AI 判断链接超时，已启用启发式辅助判断。" if _allow_heuristic_fallback()
                          else "AI 判断链接超时，未启用启发式判断。")
                tracker.log(f"第 {batch_num} 批超时。{mode_label}", "warning")
        else:
            for link, result in zip(batch, batch_results):
                judged.append({**link, **result})

        batches_done += 1
        batch_elapsed = time.time() - batch_start

        if tracker:
            tracker.metric("batches_done", batches_done)
            tracker.metric("judged_count", len(judged))
            tracker.metric("avg_batch_seconds", round((time.time() - start_time) / batches_done, 1))

    total_elapsed = round(time.time() - start_time, 1)
    if tracker:
        tracker.log(f"批量判断完成：{batches_done}/{batches_total} 批，总耗时 {total_elapsed}s", "info")

    return {
        "judged_links": judged,
        "warnings": warnings,
        "batches_total": batches_total,
        "batches_done": batches_done,
    }


def _batch_judge_with_timeout(case_detail, goals, batch, batch_num):
    """在独立线程中执行批量判断，带超时"""
    llm = get_deepseek_client()
    if not llm.enabled:
        if _is_strict_link_judge():
            # strict 模式：不启用启发式，全部标记为需人工核验
            return [_strict_timeout_judgment(link, "DeepSeek 未配置或不可用（strict 模式）")
                    for link in batch]
        elif _allow_heuristic_fallback():
            return [_judge_heuristic(case_detail, goals, link) for link in batch]
        else:
            return [_strict_timeout_judgment(link, "DeepSeek 未配置或不可用")
                    for link in batch]

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call_batch_judge_deepseek, llm, case_detail, goals, batch)
        try:
            return future.result(timeout=LINK_JUDGE_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            return None
        except Exception:
            return None


def _call_batch_judge_deepseek(llm, case_detail, goals, batch):
    """单批 DeepSeek 调用，使用鲁棒解析器"""
    links_text = ""
    for i, link in enumerate(batch, 1):
        is_pdf = ".pdf" in link.get("url", "").lower()
        pdf_note = "（PDF 文件，仅基于标题和摘要判断）" if is_pdf else ""
        links_text += (
            f"链接 {i}：\n"
            f"  标题：{link.get('title', '')}\n"
            f"  摘要：{link.get('snippet', '')}\n"
            f"  URL：{link.get('url', '')}\n"
            f"  提取文本：{link.get('extracted_text', '')[:800]}\n"
            f"  {pdf_note}\n"
        )

    prompt = f"""请批量判断以下 {len(batch)} 个在线搜索结果，为每个链接输出独立 JSON，整体放在一个 JSON 数组中。
只输出 JSON 数组，不要解释。

格式：[{{"useful":true/false, "useful_score":0.0-1.0, "result_type":"case/statute/policy/unknown", "can_support_case_argument":true/false, "can_be_legal_basis":true/false, "matched_goal":"...", "reason":"...", "risk":"...", "need_human_verify":true/false}}, ...]

案件详情：{case_detail}
用户目标：{goals}

{links_text}"""

    try:
        raw = llm._chat([
            {"role": "system", "content": "请严格输出 JSON 数组，不要输出其他内容。"},
            {"role": "user", "content": prompt},
        ], temperature=0.2, max_tokens=4096)
    except Exception:
        return None

    # 使用鲁棒解析器
    from utils.robust_json_parser import parse_batch_judgment_results, parse_link_judgment
    from utils.robust_json_parser import parse_deepseek_output

    parsed_raw, method, diag = parse_deepseek_output(raw)
    if parsed_raw is None:
        return None

    # 构建默认结果（启发式）
    default = _judge_heuristic(case_detail, goals, batch[0] if batch else {})

    return parse_batch_judgment_results(parsed_raw, batch, default)


def judge_online_link(case_detail: str, goals: List[str], link: Dict) -> Dict:
    llm = get_deepseek_client()
    if llm.enabled:
        result = _judge_with_deepseek(llm, case_detail, goals, link)
        if result:
            return result
    # AI 不可用时的处理
    if _is_strict_link_judge():
        return _strict_timeout_judgment(link, "DeepSeek 未配置或返回空（strict 模式）")
    elif _allow_heuristic_fallback():
        return _judge_heuristic(case_detail, goals, link)
    else:
        return _strict_timeout_judgment(link, "DeepSeek 未配置或返回空")


def _judge_with_deepseek(llm, case_detail: str, goals: List[str], link: Dict) -> Dict:
    prompt = f"""请判断在线搜索结果是否对当前案件有用，并分类结果类型，只输出 JSON。

硬性规则：
1. 不能把普通新闻、论坛、博客伪装成案例。
2. 案由明显不一致时 useful=false。
3. 没有明确案例信息但可能相关的，need_human_verify=true。
4. 不能伪造案号、法院、裁判观点或链接。
5. result_type 必须按以下规则判断：
   - 标题/内容含"司法解释""最高法释""法释" → judicial_interpretation
   - 含"指导性案例" → guiding_case
   - 含"典型案例" → typical_case
   - 含"裁判要旨""案号""判决书""裁定书""人民法院" → judgment
   - 含"意见""通知""办法""规定""条例"且无案号 → policy
   - 含"中华人民共和国""法""条例"且无案号 → statute
6. 司法解释/政策不能作为类案（can_support_case_argument=false）。
7. 司法解释/政策可作为法律依据（can_be_legal_basis=true）。

案件详情：
{case_detail}

用户目标：
{goals}

搜索结果：
标题：{link.get('title', '')}
摘要：{link.get('snippet', '')}
URL：{link.get('url', '')}
提取文本：{link.get('extracted_text', '')[:1500]}

输出字段：
useful, useful_score, result_type, can_support_case_argument, can_be_legal_basis,
matched_goal, matched_issue, support_strength, reason, risk, need_human_verify
"""
    data = llm._chat_json(prompt, {})
    if not isinstance(data, dict) or "useful" not in data:
        return {}
    return {
        "useful": bool(data.get("useful")),
        "useful_score": float(data.get("useful_score") or 0),
        "result_type": str(data.get("result_type", "unknown")),
        "can_support_case_argument": bool(data.get("can_support_case_argument", data.get("result_type", "") in ("case", "guiding_case", "typical_case", "judgment"))),
        "can_be_legal_basis": bool(data.get("can_be_legal_basis", data.get("result_type", "") in ("judicial_interpretation", "policy", "statute"))),
        "matched_goal": str(data.get("matched_goal", "")),
        "matched_issue": str(data.get("matched_issue", "")),
        "support_strength": str(data.get("support_strength", "弱")),
        "reason": str(data.get("reason", "")),
        "risk": str(data.get("risk", "")),
        "need_human_verify": bool(data.get("need_human_verify", True)),
    }


def _judge_heuristic(case_detail: str, goals: List[str], link: Dict) -> Dict:
    link_text = " ".join([link.get("title", ""), link.get("snippet", ""), link.get("extracted_text", "")[:1000]])
    score = overlap_score(keyword_tokens(case_detail), keyword_tokens(link_text))
    matched_goal = goals[0] if goals else ""
    goal_score = 0.0
    for goal in goals:
        current = overlap_score(keyword_tokens(goal), keyword_tokens(link_text))
        if current >= goal_score:
            matched_goal = goal
            goal_score = current
    useful_score = min(0.88, 0.42 + score * 0.3 + goal_score * 0.3)
    is_official = bool(link.get("official_source"))
    useful = is_official and useful_score >= 0.65
    if "新闻" in link_text and not any(term in link_text for term in ["案例", "裁判", "判决", "指导性案例", "典型案例"]):
        useful = False
        useful_score = min(useful_score, 0.55)

    # Classify result type heuristically
    title = link.get("title", "")
    result_type = "unknown"
    combined = f"{title} {link_text}"
    if any(kw in combined for kw in ["司法解释", "最高法释", "法释"]):
        result_type = "judicial_interpretation"
    elif "指导性案例" in combined:
        result_type = "guiding_case"
    elif "典型案例" in combined:
        result_type = "typical_case"
    elif any(kw in combined for kw in ["裁判要旨", "案号", "判决书", "裁定书", "人民法院"]):
        result_type = "judgment"
    elif any(kw in title for kw in ["意见", "通知", "办法", "规定", "条例"]):
        result_type = "policy"
    elif any(kw in title for kw in ["中华人民共和国", "法", "条例"]):
        result_type = "statute"

    return {
        "useful": useful,
        "useful_score": round(useful_score, 2),
        "result_type": result_type,
        "can_support_case_argument": useful and result_type in ("case", "guiding_case", "typical_case", "judgment"),
        "can_be_legal_basis": bool(link.get("official_source")) and result_type in ("judicial_interpretation", "policy", "statute", "case", "guiding_case", "typical_case", "judgment"),
        "matched_goal": matched_goal,
        "matched_issue": link.get("possible_holding") or link.get("snippet", "")[:80],
        "support_strength": "中" if useful_score >= 0.75 else "弱",
        "reason": "基于标题、摘要、官方来源和关键词重合度的保守判断；需人工核验后方可正式引用。",
        "risk": "未进行真实法律模型复核或页面全文核验，可能不适用当前案件。",
        "need_human_verify": True,
    }
