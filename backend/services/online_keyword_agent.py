import os
import time
from typing import Dict, List

from config import is_strict_mode, AI_FAILURE_MODE
from services.deepseek_client import get_deepseek_client
from utils.text_utils import keyword_tokens, split_goals


def generate_online_keywords(
    case_detail: str,
    goals_raw: str,
    max_keywords_per_goal: int | None = None,
    tracker=None,
    case_analysis_duration: float | None = None,
) -> Dict:
    generation_started = time.perf_counter()
    goals = split_goals(goals_raw)
    max_items = max_keywords_per_goal or int(os.getenv("MAX_SEARCH_KEYWORDS_PER_GOAL", "8"))
    llm = get_deepseek_client()
    _log(
        tracker,
        "keyword_generation_start "
        f"case_analysis_duration={_fmt_duration(case_analysis_duration)} "
        "keyword_generation_duration=0.000s deepseek_api_duration=0.000s keyword_parse_duration=0.000s",
    )
    if case_analysis_duration is not None:
        _metric(tracker, "case_analysis_duration", round(case_analysis_duration, 3))

    if llm.enabled:
        generated = _generate_with_deepseek(case_detail, goals, max_items, tracker, generation_started, case_analysis_duration)
        if generated.get("keywords"):
            duration = time.perf_counter() - generation_started
            _metric(tracker, "keyword_generation_duration", round(duration, 3))
            _metric(tracker, "keywords_count", len(generated.get("keywords", [])))
            _log(tracker,
                f"keyword_generation_done keyword_count={len(generated.get('keywords', []))} "
                f"case_analysis_duration={_fmt_duration(case_analysis_duration)} "
                f"keyword_generation_duration={duration:.3f}s "
                f"deepseek_api_duration={generated.get('_deepseek_api_duration', 0):.3f}s "
                f"keyword_parse_duration={generated.get('_keyword_parse_duration', 0):.3f}s")
            generated.pop("_deepseek_api_duration", None)
            generated.pop("_keyword_parse_duration", None)
            return generated

        # AI 失败
        fallback_reason = generated.get("warnings", ["AI 关键词生成失败"])[0]
        fallback_api_duration = float(generated.get("_deepseek_api_duration", 0))
        fallback_parse_duration = float(generated.get("_keyword_parse_duration", 0))

        if is_strict_mode():
            _log(tracker,
                f"keyword_generation_failed reason={fallback_reason} fallback=false mode={AI_FAILURE_MODE} "
                f"deepseek_api_duration={fallback_api_duration:.3f}s",
                "error")
            return {
                "keyword_groups": [], "keywords": [],
                "warnings": [f"AI 关键词生成失败: {fallback_reason}。系统处于 strict 模式，已停止检索。"],
                "failed": True, "failed_stage": "generating_keywords",
                "error_type": "deepseek_keyword_failed",
                "_deepseek_api_duration": fallback_api_duration,
                "_keyword_parse_duration": fallback_parse_duration,
            }
    else:
        fallback_reason = "DeepSeek 未配置或不可用。"
        fallback_api_duration = 0.0
        fallback_parse_duration = 0.0
        if is_strict_mode():
            _log(tracker,
                f"keyword_generation_failed reason={fallback_reason} fallback=false mode={AI_FAILURE_MODE}",
                "error")
            return {
                "keyword_groups": [], "keywords": [],
                "warnings": [f"AI 关键词生成失败: {fallback_reason}。系统处于 strict 模式，已停止检索。"],
                "failed": True, "failed_stage": "generating_keywords",
                "error_type": "deepseek_disabled",
                "_deepseek_api_duration": 0, "_keyword_parse_duration": 0,
            }

    # === 仅在非 strict 模式下才会到达这里 ===
    fallback = _generate_heuristic(case_detail, goals, max_items, fallback_reason)
    duration = time.perf_counter() - generation_started
    _metric(tracker, "keyword_generation_duration", round(duration, 3))
    _metric(tracker, "keywords_count", len(fallback.get("keywords", [])))
    _log(tracker,
        f"keyword_generation_done keyword_count={len(fallback.get('keywords', []))} "
        f"case_analysis_duration={_fmt_duration(case_analysis_duration)} "
        f"keyword_generation_duration={duration:.3f}s "
        f"deepseek_api_duration={fallback_api_duration:.3f}s "
        f"keyword_parse_duration={fallback_parse_duration:.3f}s fallback=true",
        "warning")
    return fallback


def _generate_with_deepseek(
    case_detail: str,
    goals: List[str],
    max_items: int,
    tracker=None,
    generation_started: float | None = None,
    case_analysis_duration: float | None = None,
) -> Dict:
    from config import DEEPSEEK_KEYWORD_MAX_TOKENS, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS

    llm = get_deepseek_client()

    # 统一 short prompt — 与 /api/deepseek/test-keyword-generation 完全一致
    prompt = f"""你是法律类案检索关键词生成器。请基于案件详情和希望结果，生成 6-10 个适合搜索公开裁判案例和官方案例库的中文检索关键词。

要求：
1. 每个关键词 4-20 个字。
2. 不要整句复制用户希望结果。
3. 不要输出解释，不要输出 markdown。
4. 只返回严格 JSON，不要任何其他文字。

输出格式：{{"keywords":["关键词1","关键词2"]}}

案件详情：{case_detail[:3000]}
希望结果：{goals}"""

    generation_started = generation_started or time.perf_counter()
    _log(tracker,
        f"deepseek_keyword_request_sent model={DEEPSEEK_MODEL} max_tokens={DEEPSEEK_KEYWORD_MAX_TOKENS} "
        f"prompt_length={len(prompt)} case_detail_len={len(case_detail[:3000])} goals_len={len(str(goals))} "
        f"case_analysis_duration={_fmt_duration(case_analysis_duration)} "
        f"keyword_generation_duration={time.perf_counter() - generation_started:.3f}s")

    api_started = time.perf_counter()

    # 使用 _chat_with_diagnostics 获取完整诊断
    try:
        result = llm._chat_with_diagnostics(
            [{"role": "system", "content": "你是法律检索关键词生成器。只输出 JSON，不做解释。"},
             {"role": "user", "content": prompt}],
            0.1, DEEPSEEK_KEYWORD_MAX_TOKENS,
        )
    except Exception as exc:
        api_duration = time.perf_counter() - api_started
        _log(tracker,
            f"deepseek_keyword_request_exception error={exc} "
            f"deepseek_api_duration={api_duration:.3f}s", "error")
        return {
            "keyword_groups": [], "keywords": [],
            "warnings": [f"DeepSeek 关键词生成异常: {exc}。系统处于 strict 模式，已停止检索。未启用规则关键词 fallback。"],
            "_deepseek_api_duration": api_duration, "_keyword_parse_duration": 0,
        }

    api_duration = time.perf_counter() - api_started
    d = result["diagnostics"]
    raw = result.get("content", "")
    raw_length = len(raw)
    finish = d.get("finish_reason", "?")

    _log(tracker,
        f"deepseek_keyword_response_received finish_reason={finish} content_length={d['content_length']} "
        f"completion_tokens={d['completion_tokens']} prompt_tokens={d['prompt_tokens']} "
        f"raw_length={raw_length} status_code={d['status_code']} "
        f"deepseek_api_duration={api_duration:.3f}s")

    _metric(tracker, "deepseek_api_duration", round(api_duration, 3))
    _metric(tracker, "keyword_finish_reason", finish)
    _metric(tracker, "keyword_content_length", d["content_length"])
    _metric(tracker, "keyword_completion_tokens", d["completion_tokens"])
    _metric(tracker, "keyword_raw_length", raw_length)

    # 空响应检查
    if raw_length == 0:
        _log(tracker,
            f"keyword_generation_failed reason=DeepSeek 返回空内容 finish={finish} "
            f"content_len={d['content_length']} completion_tokens={d['completion_tokens']} "
            f"msg_keys={d.get('message_keys',[])} error={d.get('error_message','')}", "error")
        return {
            "keyword_groups": [], "keywords": [],
            "warnings": [f"关键词生成失败：DeepSeek 关键词生成返回空内容（finish={finish}），系统处于 strict 模式，已停止检索。未启用规则关键词 fallback。"],
            "_deepseek_api_duration": api_duration, "_keyword_parse_duration": 0,
        }

    # 解析
    from utils.robust_json_parser import parse_robust_json, get_field
    parse_started = time.perf_counter()
    data, parse_method, diag = parse_robust_json(raw)
    parse_duration = time.perf_counter() - parse_started
    _metric(tracker, "keyword_parse_duration", round(parse_duration, 3))
    _metric(tracker, "keyword_parse_method", parse_method)

    if not isinstance(data, dict):
        _log(tracker,
            f"keyword_parse_failed parse_method={parse_method} error={diag.get('error','?')} "
            f"raw_preview={raw[:200]}", "warning")
        return {
            "keyword_groups": [], "keywords": [],
            "warnings": [f"关键词生成失败：DeepSeek 已返回内容，但关键词 JSON 解析失败（{parse_method}: {diag.get('error','?')}）。系统处于 strict 模式，已停止检索。未启用规则关键词 fallback。"],
            "_deepseek_api_duration": api_duration, "_keyword_parse_duration": parse_duration,
        }

    keywords = get_field(data, "keywords", [])
    if not keywords and "keywords" in data:
        keywords = data["keywords"]
    keywords = [str(k).strip() for k in keywords if str(k).strip()]

    keyword_groups = []
    raw_groups = get_field(data, "keyword_groups", [])
    if raw_groups:
        for group in raw_groups:
            gk = [str(k).strip() for k in get_field(group, "keywords", []) if str(k).strip()]
            keyword_groups.append({"goal": group.get("goal", ""), "keywords": gk[:max_items]})

    _log(tracker,
        f"keyword_parse_done keyword_count={len(keywords)} parse_method={parse_method} "
        f"parse_duration={parse_duration:.3f}s")

    return {
        "keyword_groups": keyword_groups,
        "keywords": keywords,
        "warnings": [],
        "_deepseek_api_duration": api_duration,
        "_keyword_parse_duration": parse_duration,
    }


def _generate_heuristic(case_detail: str, goals: List[str], max_items: int, warning: str | None = None) -> Dict:
    tokens = keyword_tokens(case_detail)
    if any(term in case_detail for term in ["劳动", "工资", "加班", "公积金", "社保", "离职"]):
        cause_terms = ["劳动争议", "劳动合同", "经济补偿", "住房公积金", "补偿协议"]
    elif any(term in case_detail for term in ["租赁", "押金", "房屋"]):
        cause_terms = ["房屋租赁合同", "押金返还", "违约责任", "解除合同"]
    else:
        cause_terms = ["合同纠纷", "违约责任", "解除合同", "赔偿损失"]

    keyword_groups = []
    all_keywords: List[str] = []
    for goal in goals:
        goal_tokens = keyword_tokens(goal)
        seeds = list(dict.fromkeys(cause_terms + goal_tokens + tokens[:8]))
        templates = [
            " ".join(seeds[:4]),
            " ".join([*seeds[:2], "裁判观点", *goal_tokens[:2]]),
            " ".join([*seeds[:3], "典型案例"]),
            " ".join([*goal_tokens[:2], *cause_terms[:3], "效力"]),
            " ".join([*cause_terms[:2], "争议焦点", *goal_tokens[:2]]),
            " ".join([*cause_terms[:2], "指导性案例"]),
            " ".join([*goal_tokens[:2], "法院", "支持条件"]),
            " ".join([*cause_terms[:3], "请求权基础"]),
        ]
        keywords = [item.strip() for item in dict.fromkeys(templates) if item.strip()][:max_items]
        keyword_groups.append({"goal": goal, "keywords": keywords})
        all_keywords.extend(keywords)

    return {
        "keyword_groups": keyword_groups,
        "keywords": list(dict.fromkeys(all_keywords)),
        "warnings": [warning or "DeepSeek 未配置或不可用，已使用保守关键词生成器。"],
    }


def _log(tracker, message: str, level: str = "info") -> None:
    if tracker:
        tracker.log(message, level)
    print(f"[keyword] {level} {message}", flush=True)


def _metric(tracker, key: str, value) -> None:
    if tracker:
        tracker.metric(key, value)


def _fmt_duration(value: float | None) -> str:
    return f"{float(value or 0):.3f}s"
