"""
引用校验 —— 检查案例引用是否可被正式引用
"""
from typing import Dict, List, Optional


class CitationChecker:
    def __init__(self):
        self._strict_mode = True

    def check(self, case: Dict) -> Dict:
        """检查单个案例是否可作为正式引用"""
        verified = case.get("verified", False)
        is_mock = case.get("is_mock", False) or str(case.get("link", "")).startswith("mock://")
        is_official = case.get("official", False) or case.get("online_indexed", False)

        can_cite = (verified and not is_mock) if self._strict_mode else (not is_mock)

        return {
            "case_id": case.get("id", case.get("case_no", "")),
            "can_be_used_as_formal_citation": can_cite,
            "verified": verified,
            "is_mock": is_mock,
            "is_official": is_official,
            "issues": [] if can_cite else [
                "未核验" if not verified else "",
                "模拟案例不可作为正式引用" if is_mock else "",
            ],
        }


_checker: Optional[CitationChecker] = None


def get_citation_checker() -> CitationChecker:
    global _checker
    if _checker is None:
        _checker = CitationChecker()
    return _checker
