"""
案例排序模块 —— 对检索结果进行相关性排序
"""

from typing import List, Dict


class CaseRanker:
    """案例排序器"""

    def rank(self, cases: List[Dict], case_detail: str, 
             keywords: List[str]) -> List[Dict]:
        """
        对案例进行多维度相关性排序

        排序维度：
        1. 关键词匹配度（权重 40%）
        2. 争议焦点相似度（权重 30%）
        3. 裁判法院级别（权重 15%）
        4. 裁判日期（权重 15%）
        """
        if not cases:
            return []

        scored_cases = []
        for case in cases:
            score = self._compute_score(case, case_detail, keywords)
            scored_cases.append((score, case))

        # 按分数降序排列
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored_cases]

    def _compute_score(self, case: Dict, case_detail: str,
                       keywords: List[str]) -> float:
        """计算单个案例的相关性分数"""
        score = 0.0

        # 1. 关键词匹配度 (40%)
        case_text = f"{case.get('title', '')} {case.get('issue', '')} {case.get('holding', '')}"
        kw_matches = sum(1 for kw in keywords if kw in case_text)
        if keywords:
            score += (kw_matches / len(keywords)) * 40

        # 2. 法院级别 (15%)
        court = case.get("court", "")
        if "最高人民法院" in court:
            score += 15
        elif "高级人民法院" in court:
            score += 12
        elif "中级人民法院" in court:
            score += 8
        elif "人民法院" in court:
            score += 5

        # 3. 裁判日期 (15%) - 越新分越高
        date_str = case.get("judgment_date", "")
        if date_str:
            try:
                year = int(date_str[:4])
                if year >= 2024:
                    score += 15
                elif year >= 2023:
                    score += 12
                elif year >= 2022:
                    score += 8
                else:
                    score += 4
            except ValueError:
                pass

        # 4. 争议焦点相似度 (30%) - 简化版
        case_issue = case.get("issue", "")
        detail_words = set(case_detail)
        issue_words = set(case_issue)
        if issue_words:
            overlap = len(detail_words & issue_words) / max(len(issue_words), 1)
            score += min(overlap * 30, 30)

        return score


def get_case_ranker() -> CaseRanker:
    return CaseRanker()
