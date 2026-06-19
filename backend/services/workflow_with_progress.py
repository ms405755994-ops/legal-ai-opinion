"""
带实时进度反馈的分析工作流
包装原有 workflow.run_analysis + online_search_workflow，每步写入进度
"""

import os
import asyncio
import time
from typing import Dict, List

from services.analyze_job_manager import ProgressTracker
from services.workflow import run_analysis, build_report_markdown
from services.online_search_workflow import (
    collect_online_links,
    preview_keywords,
    search_online_index,
    judge_links,
)
from services.deepseek_client import get_deepseek_client
from services.report_generator import get_report_generator
from services.legal_reviewer import review_legal_analysis
from services.case_search import get_case_search_engine
from services.case_ranker import get_case_ranker
from services.citation_checker import get_citation_checker
from utils.text_utils import split_goals
from utils.id_utils import short_uuid


async def run_analysis_with_progress(
    tracker: ProgressTracker,
    case_detail: str,
    goals_raw: str,
    auto_online_search: bool = True,
    only_official_sources: bool = True,
    max_keywords_per_goal: int = 8,
    max_search_results_per_keyword: int = 10,
    max_links_to_judge: int = 30,
    max_links_to_use: int = 8,
) -> Dict:
    """
    带进度的分析工作流，每一步更新 tracker。

    如果 tracker.is_cancelled() 返回 True，则提前终止。
    """
    try:
        return await _run_analysis_with_progress_impl(
            tracker=tracker,
            case_detail=case_detail,
            goals_raw=goals_raw,
            auto_online_search=auto_online_search,
            only_official_sources=only_official_sources,
            max_keywords_per_goal=max_keywords_per_goal,
            max_search_results_per_keyword=max_search_results_per_keyword,
            max_links_to_judge=max_links_to_judge,
            max_links_to_use=max_links_to_use,
        )
    except _JobCancelledError:
        raise
    except Exception as exc:
        tracker.log(f"后台任务异常：{exc}", "error")
        tracker.set_error(str(exc))
        raise


async def _run_analysis_with_progress_impl(
    tracker: ProgressTracker,
    case_detail: str,
    goals_raw: str,
    auto_online_search: bool = True,
    only_official_sources: bool = True,
    max_keywords_per_goal: int = 8,
    max_search_results_per_keyword: int = 10,
    max_links_to_judge: int = 30,
    max_links_to_use: int = 8,
) -> Dict:
    goals = split_goals(goals_raw)
    analysis_id = short_uuid("ana_")
    warnings: List[str] = []
    provider = os.getenv("ONLINE_SEARCH_PROVIDER", "tavily")

    # ── Step 1: 案件拆解 ────────────────────────────
    _check_cancel(tracker)
    tracker.update_step("analyzing_case", "正在拆解案件", 1, 8)
    tracker.log("开始拆解案件")

    llm = get_deepseek_client()
    case_analysis_started = time.perf_counter()
    decompose_result = llm.decompose_case(case_detail, goals)
    case_analysis_duration = time.perf_counter() - case_analysis_started
    tracker.metric("case_analysis_duration", round(case_analysis_duration, 3))

    cause = decompose_result.get("cause_of_action", "")
    tracker.log(
        f"案件拆解完成：{cause} case_analysis_duration={case_analysis_duration:.3f}s" if cause else f"案件拆解完成 case_analysis_duration={case_analysis_duration:.3f}s"
    )
    tracker.metric("cause_of_action", cause)
    tracker.metric("keywords_count", 0)

    # ── Step 2: 关键词生成 ──────────────────────────
    _check_cancel(tracker)
    tracker.update_step("generating_keywords", "正在生成检索关键词", 2, 20)
    tracker.log("正在等待 DeepSeek 生成检索关键词，Tavily 尚未开始搜索。")

    keyword_result: Dict = {"keywords": [], "keyword_groups": []}
    search_summary: Dict = {
        "provider": provider,
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

    if auto_online_search:
        # 在线搜索模式 —— 关键词预览
        kw_preview = preview_keywords(
            case_detail,
            goals_raw,
            max_keywords_per_goal,
            tracker=tracker,
            case_analysis_duration=case_analysis_duration,
        )

        # ── strict 模式：关键词生成失败则立即停止 ──
        if kw_preview.get("failed"):
            tracker.log(
                f"AI 关键词生成失败: {kw_preview.get('warnings', ['未知错误'])[0]}",
                "error"
            )
            tracker.set_error(f"关键词生成失败: {kw_preview.get('warnings', ['未知错误'])[0]}")
            return {
                "success": False,
                "analysis_id": analysis_id,
                "html": "",
                "markdown": "",
                "cases": [],
                "review": {},
                "warnings": kw_preview.get("warnings", []),
                "error": kw_preview.get("warnings", ["AI 关键词生成失败"])[0],
            }

        keyword_result = {
            "keywords": kw_preview.get("keywords", []),
            "keyword_groups": kw_preview.get("keyword_groups", []),
        }
        warnings.extend(kw_preview.get("warnings", []))
        keywords_count = len(keyword_result["keywords"])
        tracker.log(f"已生成 {keywords_count} 个检索关键词")
        tracker.metric("keywords_count", keywords_count)
        tracker.update_step("generating_keywords", "关键词生成完成", 2, 25)

        # ── Step 3: 在线搜索 ────────────────────────
        _check_cancel(tracker)
        tracker.update_step("searching_official_sources", "正在搜索官方案例来源", 3, 30)

        search_result = search_online_index(
            keywords=keyword_result["keywords"],
            sources=[],
            provider=provider,
            max_results_per_keyword=max_search_results_per_keyword,
            tracker=tracker,
        )
        raw_count = search_result.get("total_raw_results", len(search_result.get("search_results", [])))
        official_count = search_result.get("official_results", raw_count)
        tracker.metric("raw_results_count", raw_count)
        tracker.metric("official_results_count", official_count)
        tracker.metric("queries_done_count", search_result.get("total_queries", 0))

        tracker.update_step("searching_official_sources", "搜索完成", 3, 40)

        # ── Step 4: 官方来源过滤 ─────────────────────
        _check_cancel(tracker)
        tracker.update_step("filtering_official_links", "正在筛选官方来源链接", 4, 45)
        official_results = search_result.get("search_results", [])
        tracker.log(f"开始官方来源过滤：共 {raw_count} 条搜索结果")
        tracker.log(f"官方来源过滤完成：{raw_count} 条中保留 {official_count} 条，过滤 {raw_count - official_count} 条")
        tracker.metric("official_results_count", official_count)
        tracker.update_step("filtering_official_links", "官方来源过滤完成", 4, 50)

        # ── Step 5: AI 批量判断链接 ──────────────────
        _check_cancel(tracker)
        tracker.update_step("judging_links", "AI 正在批量判断链接相关性", 5, 55)

        if official_results:
            judge_limit = min(max_links_to_judge, len(official_results))
            tracker.log(f"开始 AI 批量判断链接：{judge_limit} 条，分批处理")

            from config import LINK_JUDGE_BATCH_SIZE, LINK_JUDGE_TIMEOUT_SECONDS, LINK_JUDGE_TOTAL_TIMEOUT_SECONDS, SKIP_PDF_DIRECT_EXTRACT
            from services.online_case_extractor import extract_online_case
            from services.online_case_judge import batch_judge_links

            # 预处理：识别 PDF 链接并跳过正文提取
            prepped_links = []
            for link in official_results[:judge_limit]:
                is_pdf = ".pdf" in link.get("url", "").lower()
                if is_pdf and SKIP_PDF_DIRECT_EXTRACT:
                    link["extracted_text"] = ""
                    link["skipped_reason"] = "PDF 链接仅基于标题和摘要判断，未解析正文。"
                    tracker.log(f"PDF 链接跳过正文提取：{link.get('title', link.get('url', '?'))[:50]}", "info")
                elif not link.get("extracted_text"):
                    extracted = extract_online_case(link)
                    if extracted.get("skipped_reason"):
                        link["skipped_reason"] = extracted["skipped_reason"]
                    else:
                        link["extracted_text"] = extracted.get("extracted_text", "")
                prepped_links.append(link)

            # 批量判断
            judge_result = batch_judge_links(
                case_detail=case_detail,
                goals_raw=goals_raw,
                links=prepped_links,
                max_links=judge_limit,
                tracker=tracker,
            )

            judged_links = judge_result.get("judged_links", [])
            judged_count = len(judged_links)
            useful_count = sum(
                1 for jl in judged_links
                if jl.get("useful") and float(jl.get("useful_score", 0)) >= 0.65
            )

            tracker.log(f"批量判断完成：共 {judged_count} 条，有用 {useful_count} 条")
            tracker.metric("links_judged_count", judged_count)
            tracker.metric("useful_links_count", useful_count)
            tracker.metric("batches_total", judge_result.get("batches_total", 0))
            tracker.metric("batches_done", judge_result.get("batches_done", 0))

            useful_links_list = [
                item for item in judged_links
                if item.get("useful") and float(item.get("useful_score", 0)) >= 0.65
            ]

            from services.case_link_store import get_case_link_store
            stored = get_case_link_store().save_judged_links(
                useful_links_list, max_links_to_use,
                analysis_id=analysis_id, auto_collected=True, used_in_analysis=True,
            )
            used_links = stored
        else:
            tracker.log("无搜索结果可供 AI 判断")
            tracker.metric("links_judged_count", 0)
            tracker.metric("useful_links_count", 0)
            judged_count = 0
            useful_count = 0

        tracker.update_step("judging_links", "AI 判断完成", 5, 65)

        # 汇总
        search_summary = {
            "provider": provider,
            "provider_ready": bool(search_result.get("provider_ready")),
            "total_queries": search_result.get("total_queries", 0),
            "total_raw_results": raw_count,
            "official_results": official_count,
            "links_judged": judged_count if official_results else 0,
            "useful_links": useful_count if official_results else 0,
            "used_in_report": len(used_links),
        }
        verified_cases = [_link_to_case_reference(link) for link in used_links]
    else:
        # mock 模式
        tracker.log("离线模式：生成关键词并检索模拟案例")
        keyword_result = llm.generate_search_keywords(case_detail, goals, decompose_result)
        keywords = _flatten_keywords(keyword_result)
        tracker.log(f"已生成 {len(keywords)} 个检索关键词")
        tracker.metric("keywords_count", len(keywords))

        search_result = get_case_search_engine().search_cases(case_detail, goals, keywords, top_k=10)
        warnings.extend(search_result["warnings"])
        rank_result = get_case_ranker().rank_cases(case_detail, goals, search_result["cases"])
        warnings.extend(rank_result["warnings"])
        citation_result = get_citation_checker().verify(rank_result["ranked_cases"])
        warnings.extend(citation_result["warnings"])
        verified_cases = citation_result["verified_cases"]
        tracker.log(f"检索到 {len(verified_cases)} 个案例")

    # ── Step 6: 生成报告 ────────────────────────────
    _check_cancel(tracker)
    tracker.update_step("generating_report", "正在生成案件处理思路报告", 6, 75)
    tracker.log("正在生成案件处理思路...")

    case_mode_info = _case_mode_info(verified_cases)
    tracker.metric("used_links_count", len(used_links))

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

    tracker.log("报告生成完成")
    tracker.update_step("generating_report", "报告生成完成", 6, 90)

    # ── Step 7: 生成 Word ───────────────────────────
    _check_cancel(tracker)
    tracker.update_step("generating_word", "正在生成 Word 文档", 6, 92)
    tracker.log("正在生成 Word...")

    from config import WORD_EXPORT_TIMEOUT_SECONDS

    # 使用同步方式在线程中运行（report_generator 是同步的），带超时
    loop = asyncio.get_event_loop()
    try:
        docx_file_id, _filename = await asyncio.wait_for(
            loop.run_in_executor(
                None, get_report_generator().generate, final_markdown, verified_cases
            ),
            timeout=WORD_EXPORT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        tracker.log(f"Word 导出超时（>{WORD_EXPORT_TIMEOUT_SECONDS}s），任务失败", "error")
        tracker.set_error(f"Word 导出阶段超时（>{WORD_EXPORT_TIMEOUT_SECONDS}s）")
        return {
            "success": False,
            "analysis_id": analysis_id,
            "html": _markdown_to_simple_html(final_markdown),
            "markdown": final_markdown,
            "cases": verified_cases,
            "review": review,
            "warnings": list(dict.fromkeys(warnings)),
            "error": f"Word 导出超时（>{WORD_EXPORT_TIMEOUT_SECONDS}s）",
            "failed_stage": "generating_word",
            "error_type": "stage_timeout",
        }
    tracker.log("Word 生成完成")
    tracker.metric("docx_file_id", docx_file_id)
    tracker.update_step("generating_word", "Word 生成完成", 6, 98)

    # ── 完成 ────────────────────────────────────────
    _check_cancel(tracker)
    result = {
        "success": True,
        "analysis_id": analysis_id,
        "html": _markdown_to_simple_html(final_markdown),
        "markdown": final_markdown,
        "cases": verified_cases,
        "review": review,
        "warnings": list(dict.fromkeys(warnings)),
        "docx_file_id": docx_file_id,
        "case_search_mode": "online_auto" if auto_online_search else "mock",
        "auto_online_search": auto_online_search,
        "keywords": keyword_result.get("keywords", []),
        "search_summary": search_summary,
        "used_links": used_links,
        **case_mode_info,
    }
    tracker.set_result(result)
    tracker.log("🎉 全部分析流程完成")
    return result


# ── 工具函数 ─────────────────────────────────────────

def _check_cancel(tracker: ProgressTracker) -> None:
    """检查是否已取消，如果取消则抛出异常"""
    if tracker.is_cancelled():
        raise _JobCancelledError("任务已被用户取消")


class _JobCancelledError(Exception):
    """任务取消异常"""
    pass


def _link_to_case_reference(link: Dict) -> Dict:
    return {
        "id": link.get("id", ""),
        "title": link.get("title", ""),
        "case_no": link.get("case_no", ""),
        "court": link.get("court", ""),
        "judgment_date": link.get("judgment_date", ""),
        "issue": link.get("issue", ""),
        "holding": link.get("holding", ""),
        "url": link.get("url", ""),
        "source_name": link.get("source_name", ""),
        "verified": link.get("verified", False),
        "is_mock": link.get("is_mock", False),
    }


def _flatten_keywords(keyword_result: Dict) -> List[str]:
    keywords = []
    for group in keyword_result.get("keyword_groups", []):
        for field in ("cause_keywords", "issue_keywords", "holding_keywords", "winning_direction_keywords"):
            keywords.extend(group.get(field, []))
    keywords.extend(keyword_result.get("global_keywords", []))
    return list(dict.fromkeys(keywords))


def _case_mode_info(cases: List[Dict]) -> Dict:
    real_cases = [c for c in cases if not c.get("is_mock")]
    mock_cases = [c for c in cases if c.get("is_mock")]
    verified = [c for c in real_cases if c.get("verified")]
    no_cases_at_all = len(real_cases) == 0 and len(mock_cases) == 0
    return {
        "can_be_used_for_real_case": len(verified) > 0,
        "real_case_count": len(real_cases),
        "mock_case_count": len(mock_cases),
        "verified_case_count": len(verified),
        "unverified_case_count": len(real_cases) - len(verified),
        "case_mode": (
            "none" if no_cases_at_all
            else ("mock" if not real_cases
                  else ("online_verified" if verified else "online_unverified"))
        ),
        "report_mode": (
            "no_real_links" if no_cases_at_all
            else ("test_mock" if not real_cases
                  else ("online_verified" if verified else "online_unverified"))
        ),
    }


def _markdown_to_simple_html(md: str) -> str:
    import re
    html = md
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = html.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
    return f'<div class="analysis-content">{html}</div>'
