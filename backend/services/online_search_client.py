import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.official_source_filter import filter_official_result, load_online_sources
from services.search_providers.bing_search import search_bing
from services.search_providers.google_cse import search_google_cse
from services.search_providers.tavily_search import search_tavily
from utils.file_utils import read_json, write_json


BACKEND_DIR = Path(__file__).resolve().parents[1]
ONLINE_SEARCH_LOGS_FILE = BACKEND_DIR / "data" / "online_search_logs.json"


class OnlineSearchClient:
    def search(
        self,
        keywords: List[str],
        source_ids: List[str] | None = None,
        provider: str | None = None,
        max_results_per_keyword: int | None = None,
        tracker: Optional[object] = None,  # ProgressTracker
    ) -> Dict:
        provider = (provider or os.getenv("ONLINE_SEARCH_PROVIDER", "tavily")).lower()
        max_results = max_results_per_keyword or int(os.getenv("MAX_SEARCH_RESULTS_PER_KEYWORD", "10"))
        sources = load_online_sources(enabled_only=True)
        if source_ids:
            wanted = set(source_ids)
            sources = [source for source in sources if source.get("id") in wanted]

        keywords_count = len(keywords)
        sources_count = len(sources)
        total_possible_queries = keywords_count * sources_count
        max_possible_results = total_possible_queries * max_results

        # 初始日志
        provider_label = provider.title()
        if tracker:
            tracker.log(
                f"{provider_label} 开始在线搜索，共 {keywords_count} 个关键词，"
                f"{sources_count} 个官方来源，预计最多 {max_possible_results} 条候选结果"
            )
            tracker.metric("keywords_count", keywords_count)
            tracker.metric("sources_count", sources_count)
            tracker.metric("queries_count", total_possible_queries)

        warnings: List[str] = []
        skipped: List[Dict] = []
        collected: List[Dict] = []
        seen_urls = set()
        total_queries = 0
        total_raw_results = 0
        queries_done = 0
        source_result_map: Dict[str, int] = {}  # source_name → result_count

        for keyword in keywords:
            for source in sources:
                source_name = source.get("name", source.get("id", "?"))
                query = f"{source.get('search_query_prefix', '')} {keyword}".strip()
                total_queries += 1

                # 逐 query 日志：开始搜索
                if tracker:
                    tracker.log(f"正在搜索：{source_name}｜{query}")
                    tracker.metric("queries_done_count", queries_done)

                try:
                    provider_result = self._provider_search(provider, query, max_results)
                except Exception as exc:
                    if tracker:
                        tracker.log(
                            f"搜索失败：{source_name}｜{query}｜原因：{exc}",
                            "error"
                        )
                    warnings.append(f"搜索失败 {source_name}: {exc}")
                    queries_done += 1
                    continue

                warnings.extend(provider_result.get("warnings", []))
                raw_results = provider_result.get("results", [])
                result_count = len(raw_results)
                total_raw_results += result_count
                queries_done += 1

                # 逐 query 日志：搜索完成
                if tracker:
                    tracker.log(f"搜索完成：{source_name}｜返回 {result_count} 条结果")
                    tracker.metric("queries_done_count", queries_done)
                    tracker.metric("raw_results_count", total_raw_results)

                # 统计每个来源的结果数
                source_result_map[source_name] = source_result_map.get(source_name, 0) + result_count

                for raw in raw_results:
                    filtered = filter_official_result(raw, [source])
                    if not filtered["allowed"]:
                        skipped.append({"url": raw.get("url", ""), "reason": filtered["reason"]})
                        continue
                    item = filtered["result"]
                    if item.get("url") in seen_urls:
                        continue
                    seen_urls.add(item.get("url"))
                    item["keyword"] = keyword
                    item["query"] = query
                    collected.append(item)

        # 按来源汇总日志
        if tracker:
            for src_name in sorted(source_result_map.keys()):
                tracker.log(f"  └ {src_name}：累计 {source_result_map[src_name]} 条", "info")

        self._append_log(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "provider": provider,
                "keywords": keywords,
                "sources": [source.get("id") for source in sources],
                "result_count": len(collected),
                "skipped_count": len(skipped),
                "warnings": warnings,
            }
        )

        provider_ready = not any("未配置" in warning for warning in warnings)
        return {
            "search_results": collected,
            "skipped": skipped,
            "warnings": list(dict.fromkeys(warnings)),
            "provider": provider,
            "provider_ready": provider_ready,
            "total_queries": total_queries,
            "total_raw_results": total_raw_results,
            "official_results": len(collected),
        }

    def logs(self) -> List[Dict]:
        return read_json(ONLINE_SEARCH_LOGS_FILE, [])

    def _provider_search(self, provider: str, query: str, max_results: int) -> Dict:
        if provider == "tavily":
            return search_tavily(query, max_results)
        if provider == "google_cse":
            return search_google_cse(query, max_results)
        return search_bing(query, max_results)

    @staticmethod
    def _append_log(entry: Dict) -> None:
        logs = read_json(ONLINE_SEARCH_LOGS_FILE, [])
        logs.append(entry)
        write_json(ONLINE_SEARCH_LOGS_FILE, logs[-200:])


_client: OnlineSearchClient | None = None


def get_online_search_client() -> OnlineSearchClient:
    global _client
    if _client is None:
        _client = OnlineSearchClient()
    return _client
