"""
法律分析编排器 —— 串联整个分析流程
"""

import uuid
import re
from typing import List, Dict, Tuple

from services.deepseek_client import get_deepseek_client
from services.case_search import get_case_search_engine
from services.case_ranker import get_case_ranker


class LegalAnalyzer:
    """法律分析编排器"""

    def __init__(self) -> None:
        self.llm = get_deepseek_client()
        self.search_engine = get_case_search_engine()
        self.ranker = get_case_ranker()

    def analyze(self, case_detail: str, goals_raw: str) -> Dict:
        """
        完整分析流程：

        1. 拆分期望值
        2. AI 拆解案件
        3. AI 生成各目标法律路径
        4. 提取关键词 → 检索案例
        5. 案例排序
        6. AI 生成完整报告（仅使用真实案例）
        7. 组装返回
        """
        analysis_id = str(uuid.uuid4())[:8]
        warnings: List[str] = []
        goals = self._split_goals(goals_raw)

        # ── Step 1 & 2: AI 拆解案件 ──
        case_decomp = self.llm.decompose_case(case_detail)
        if case_decomp.get("parse_error"):
            warnings.append("案件拆解 JSON 解析失败，使用原始输出")

        # ── Step 3: AI 生成各目标法律路径 ──
        goal_paths = self.llm.generate_goal_paths(case_detail, goals)
        if goal_paths.get("parse_error"):
            warnings.append("目标路径 JSON 解析失败，使用原始输出")

        # ── Step 4: 提取关键词 → 检索案例 ──
        all_keywords = self._extract_keywords(case_decomp, goal_paths)
        raw_cases = self.search_engine.search(all_keywords, top_k=10)

        # ── Step 5: 案例排序 ──
        ranked_cases = self.ranker.rank(raw_cases, case_detail, all_keywords)

        # 检查是否有真实案例
        real_cases = [c for c in ranked_cases if not c.get("is_mock")]
        if not real_cases:
            warnings.append(
                "⚠️ 当前未检索到可核验的真实案例。报告中引用的案例均为模拟案例（Mock），"
                "仅供参考，不能作为正式法律依据。请在 backend/.env 中配置 DeepSeek API Key "
                "并在 data/sources.json 中启用真实数据源后重试。"
            )
        mock_count = sum(1 for c in ranked_cases if c.get("is_mock"))
        if mock_count > 0:
            warnings.append(f"注意：当前有 {mock_count} 个案例为模拟案例（Mock），已在报告中标注。")

        # ── Step 6: AI 生成完整报告 ──
        markdown_report = self.llm.generate_full_report(
            case_detail, goals, case_decomp, goal_paths, ranked_cases
        )

        # ── Step 7: 生成 HTML ──
        html = self._markdown_to_html(markdown_report)

        # ── 格式化案例列表 ──
        cases_output = []
        for c in ranked_cases:
            cases_output.append({
                "title": c.get("title", ""),
                "case_no": c.get("case_no", ""),
                "court": c.get("court", ""),
                "judgment_date": c.get("judgment_date", ""),
                "issue": c.get("issue", ""),
                "holding": c.get("holding", ""),
                "url": c.get("url", ""),
                "source_name": c.get("source_name", ""),
                "is_mock": c.get("is_mock", False),
            })

        return {
            "success": True,
            "analysis_id": analysis_id,
            "html": html,
            "markdown": markdown_report,
            "cases": cases_output,
            "warnings": warnings,
        }

    # ── 工具方法 ───────────────────────────────────────

    @staticmethod
    def _split_goals(goals_raw: str) -> List[str]:
        """按中文逗号、英文逗号拆分期望值"""
        goals = re.split(r"[，,]", goals_raw)
        return [g.strip() for g in goals if g.strip()]

    @staticmethod
    def _extract_keywords(case_decomp: Dict, goal_paths: Dict) -> List[str]:
        """从拆解结果和目标路径中提取所有关键词"""
        keywords = set()

        # 从案件拆解中提取
        for kw in case_decomp.get("search_keywords", []):
            keywords.add(kw)

        # 从目标路径中提取
        for ga in goal_paths.get("goals_analysis", []):
            for kw in ga.get("keywords", []):
                keywords.add(kw)
        for kw in goal_paths.get("global_keywords", []):
            keywords.add(kw)

        return list(keywords)

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """简易 Markdown → HTML（适合前端直接渲染）"""
        # 这里做基础转换，前端可以用 marked.js 做更完整渲染
        html = md

        # 标题
        html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # 粗体
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        
        # 无序列表
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)

        # 段落
        html = re.sub(r'\n\n', r'<br/><br/>', html)
        html = re.sub(r'\n', r'<br/>', html)

        return f'<div class="analysis-content">{html}</div>'


def get_legal_analyzer() -> LegalAnalyzer:
    return LegalAnalyzer()
