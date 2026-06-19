import os
from typing import Dict, List

from services.case_link_store import get_case_link_store
from services.official_source_filter import load_online_sources
from services.online_case_extractor import extract_online_case
from services.online_case_judge import judge_online_links
from services.online_keyword_agent import generate_online_keywords
from services.online_search_client import get_online_search_client


def preview_keywords(case_detail: str, goals: str, max_keywords_per_goal: int | None = None) -> Dict:
    return generate_online_keywords(case_detail, goals, max_keywords_per_goal)


def search_online_index(
    keywords: List[str],
    sources: List[str] | None = None,
    provider: str | None = None,
    max_results_per_keyword: int | None = None,
    tracker=None,
) -> Dict:
    return get_online_search_client().search(
        keywords=keywords,
        source_ids=sources or [],
        provider=provider,
        max_results_per_keyword=max_results_per_keyword,
        tracker=tracker,
    )


def judge_links(case_detail: str, goals: str, links: List[Dict], max_links_to_judge: int | None = None) -> Dict:
    max_links = max_links_to_judge or int(os.getenv("MAX_LINKS_TO_JUDGE", "30"))
    extracted_links = []
    skipped = []
    for link in links[:max_links]:
        extracted = extract_online_case(link)
        if extracted.get("skipped_reason"):
            skipped.append({"url": extracted.get("url", ""), "reason": extracted["skipped_reason"]})
        extracted_links.append(extracted)
    judged = judge_online_links(case_detail, goals, extracted_links, max_links)
    return {**judged, "skipped": skipped}


def collect_online_links(
    case_detail: str,
    goals: str,
    sources: List[str],
    provider: str | None,
    max_keywords_per_goal: int | None,
    max_results_per_keyword: int | None,
    max_links_to_judge: int | None,
    max_links_to_store: int | None,
    analysis_id: str | None = None,
    auto_collected: bool = False,
    used_in_analysis: bool = False,
) -> Dict:
    keyword_result = preview_keywords(case_detail, goals, max_keywords_per_goal)
    search_result = search_online_index(
        keywords=keyword_result.get("keywords", []),
        sources=sources,
        provider=provider,
        max_results_per_keyword=max_results_per_keyword,
    )
    judge_result = judge_links(
        case_detail=case_detail,
        goals=goals,
        links=search_result.get("search_results", []),
        max_links_to_judge=max_links_to_judge,
    )
    store_limit = max_links_to_store or int(os.getenv("MAX_LINKS_TO_USE", "8"))
    useful_links = [
        item
        for item in judge_result.get("judged_links", [])
        if item.get("useful") and float(item.get("useful_score", 0)) >= 0.65
    ]
    stored_links = get_case_link_store().save_judged_links(
        useful_links,
        store_limit,
        analysis_id=analysis_id,
        auto_collected=auto_collected,
        used_in_analysis=used_in_analysis,
    )
    warnings = []
    warnings.extend(keyword_result.get("warnings", []))
    warnings.extend(search_result.get("warnings", []))
    warnings.extend(judge_result.get("warnings", []))
    return {
        "success": True,
        "keywords": keyword_result.get("keywords", []),
        "keyword_groups": keyword_result.get("keyword_groups", []),
        "search_results": search_result.get("search_results", []),
        "judged_links": judge_result.get("judged_links", []),
        "stored_links": stored_links,
        "skipped": search_result.get("skipped", []) + judge_result.get("skipped", []),
        "warnings": list(dict.fromkeys(warnings)),
        "search_summary": {
            "provider": search_result.get("provider", provider or os.getenv("ONLINE_SEARCH_PROVIDER", "bing")),
            "provider_ready": bool(search_result.get("provider_ready")),
            "total_queries": search_result.get("total_queries", 0),
            "total_raw_results": search_result.get("total_raw_results", 0),
            "official_results": search_result.get("official_results", len(search_result.get("search_results", []))),
            "links_judged": len(judge_result.get("judged_links", [])),
            "useful_links": len(useful_links),
            "used_in_report": len(stored_links),
        },
    }


def online_sources() -> List[Dict]:
    return load_online_sources(enabled_only=False)
