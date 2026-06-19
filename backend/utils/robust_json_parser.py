"""鲁棒 JSON 解析器 —— 兼容 DeepSeek 多种输出格式"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ── 主解析入口 ────────────────────────────────────────

def parse_deepseek_output(raw: str, context: str = "unknown") -> Tuple[Optional[Any], str, Dict]:
    """
    多策略解析 DeepSeek 原始输出。

    返回：(parsed_data, method, diagnostics)
      parsed_data: 解析结果（dict/list/None）
      method: 使用的解析方式
      diagnostics: { raw_length, method, error, snippet }
    """
    diag: Dict[str, Any] = {
        "raw_length": len(raw or ""),
        "method": "none",
        "error": None,
        "snippet": (raw or "")[:300],
    }

    if not raw or not raw.strip():
        diag["error"] = "空输入"
        return None, "empty", diag

    raw = raw.strip()

    # ── 策略 1: 纯 JSON ──
    try:
        parsed = json.loads(raw)
        diag["method"] = "json"
        return parsed, "json", diag
    except json.JSONDecodeError:
        pass

    # ── 策略 2: ```json 代码块 ──
    for marker in ("```json", "```"):
        if marker in raw:
            start = raw.find(marker) + len(marker)
            end = raw.find("```", start)
            if end != -1:
                snippet = raw[start:end].strip()
                try:
                    parsed = json.loads(snippet)
                    diag["method"] = "codeblock"
                    return parsed, "codeblock", diag
                except json.JSONDecodeError:
                    pass

    # ── 策略 3: 提取 { } 块 ──
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            parsed = json.loads(raw[first:last + 1])
            diag["method"] = "brace_extract"
            return parsed, "brace_extract", diag
        except json.JSONDecodeError:
            pass

    # ── 策略 3b: 提取 [ ] 数组 ──
    first_arr = raw.find("[")
    last_arr = raw.rfind("]")
    if first_arr != -1 and last_arr != -1 and last_arr > first_arr:
        try:
            parsed = json.loads(raw[first_arr:last_arr + 1])
            diag["method"] = "bracket_extract"
            return parsed, "bracket_extract", diag
        except json.JSONDecodeError:
            pass

    # ── 策略 4: 编号列表提取关键词 ──
    numbered = _extract_numbered_list(raw)
    if len(numbered) >= 3:
        diag["method"] = "numbered_list"
        return numbered, "numbered_list", diag

    # ── 策略 5: 中文分隔符拆分 ──
    delimited = _extract_delimited(raw)
    if len(delimited) >= 3:
        diag["method"] = "delimited"
        return delimited, "delimited", diag

    diag["error"] = "所有解析策略均失败"
    return None, "all_failed", diag


# ── 专用于 JSON 修复后解析 ────────────────────────────

def parse_robust_json(raw: str) -> Tuple[Optional[Dict], str, Dict]:
    """解析必须返回 dict 的场景，额外尝试字段名修复"""
    data, method, diag = parse_deepseek_output(raw, "json_dict")

    if isinstance(data, dict):
        return data, method, diag

    if isinstance(data, list):
        return {"items": data}, method, diag

    # 最终 fallback
    diag["error"] = diag.get("error") or "无法解析为 dict"
    return None, method, diag


# ── 字段名容错 ────────────────────────────────────────

FIELD_ALIASES = {
    "keywords": ["keywords", "search_keywords", "queries", "keyword_list", "terms", "key_phrases"],
    "keyword_groups": ["keyword_groups", "groups", "goal_groups"],
    "useful": ["useful", "is_useful", "relevant", "is_relevant"],
    "useful_score": ["useful_score", "score", "relevance_score", "confidence"],
    "result_type": ["result_type", "type", "link_type", "category"],
    "matched_goal": ["matched_goal", "goal", "target"],
    "matched_issue": ["matched_issue", "issue"],
    "support_strength": ["support_strength", "support", "strength"],
    "reason": ["reason", "justification", "explanation"],
    "risk": ["risk", "risks"],
    "need_human_verify": ["need_human_verify", "needs_verification", "verify"],
    "results": ["results", "links", "judgments", "items"],
    "url": ["url", "link"],
    "title": ["title", "name"],
}


def get_field(data: Dict, canonical: str, default: Any = None) -> Any:
    """根据字段名别名从 dict 中取值"""
    aliases = FIELD_ALIASES.get(canonical, [canonical])
    for alias in aliases:
        if alias in data:
            return data[alias]
    return default


# ── 中文分数转换 ──────────────────────────────────────

def parse_chinese_score(value: Any) -> float:
    """将中文评分转为数值"""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    v = value.strip()
    mapping = {
        "强": 0.85, "高": 0.85, "很高": 0.90, "极高": 0.95,
        "中": 0.65, "中等": 0.65, "一般": 0.55,
        "弱": 0.40, "低": 0.40, "较低": 0.30, "很低": 0.20,
        "不相关": 0.10, "无关": 0.05,
    }
    for cn, num in mapping.items():
        if cn in v:
            return num
    try:
        return float(v)
    except ValueError:
        return 0.0


# ── 辅助解析 ──────────────────────────────────────────

def _extract_numbered_list(text: str) -> List[str]:
    """从编号列表中提取条目"""
    lines = text.split("\n")
    items = []
    pattern = re.compile(r"^\s*(?:\d+[\.\)、]|[-•·])\s*(.+)")
    for line in lines:
        m = pattern.match(line)
        if m:
            item = m.group(1).strip()
            if item and len(item) >= 2:
                items.append(item)
    return items


def _extract_delimited(text: str) -> List[str]:
    """从中文分隔符文本中提取关键词"""
    # 尝试按逗号/顿号/分号拆分
    parts = re.split(r"[，,、;；\n]", text)
    items = []
    for p in parts:
        p = p.strip().strip('"').strip("'").strip("。").strip(".")
        if p and len(p) >= 2:
            items.append(p)
    return items


# ── 链接判断结果解析 ──────────────────────────────────

def parse_link_judgment(raw_item: Dict, link_original: Dict) -> Dict:
    """将 DeepSeek 返回的链接判断 item 标准化"""
    result = {}

    # useful
    useful_val = get_field(raw_item, "useful")
    if useful_val is None:
        useful_val = True  # 默认假定有用
    result["useful"] = bool(useful_val)

    # useful_score
    score_val = get_field(raw_item, "useful_score", 0)
    result["useful_score"] = float(parse_chinese_score(score_val))

    # result_type
    rt = get_field(raw_item, "result_type", "unknown")
    result["result_type"] = str(rt)

    # can_support / can_be_legal_basis
    result["can_support_case_argument"] = result["result_type"] in ("case", "guiding_case", "typical_case", "judgment")
    result["can_be_legal_basis"] = result["result_type"] in ("judicial_interpretation", "policy", "statute", "case", "guiding_case", "typical_case", "judgment")

    # matched_goal
    result["matched_goal"] = str(get_field(raw_item, "matched_goal", link_original.get("matched_goal", "")))

    # matched_issue
    result["matched_issue"] = str(get_field(raw_item, "matched_issue", ""))

    # support_strength
    strength = get_field(raw_item, "support_strength", "弱")
    result["support_strength"] = str(strength)

    # reason
    result["reason"] = str(get_field(raw_item, "reason", ""))

    # risk
    result["risk"] = str(get_field(raw_item, "risk", ""))

    # need_human_verify
    verify = get_field(raw_item, "need_human_verify")
    if verify is None:
        verify = True
    result["need_human_verify"] = bool(verify)

    # parse_failed flag
    result["parse_failed"] = raw_item.get("parse_failed", False)

    return result


def parse_batch_judgment_results(raw: Any, batch_links: List[Dict], default_result: Dict) -> List[Dict]:
    """解析批量判断结果，容错处理每条链接"""
    results_list = []

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = get_field(raw, "results", [])
        if not items:
            # 尝试整个 dict 是一个结果
            items = [raw]
    else:
        # 完全失败
        return [default_result for _ in batch_links]

    for i in range(len(batch_links)):
        if i < len(items) and isinstance(items[i], dict):
            results_list.append(parse_link_judgment(items[i], batch_links[i]))
        else:
            # 单条解析失败，标记
            fallback = dict(default_result)
            fallback["parse_failed"] = True
            fallback["need_human_verify"] = True
            results_list.append(fallback)

    return results_list
