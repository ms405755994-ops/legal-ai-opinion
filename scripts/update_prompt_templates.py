"""Script to update prompt_templates.py with new sections and utilities"""
import re

path = r'd:\2026GS\FL\legal-ai-opinion\backend\services\prompt_templates.py'
src = open(path, 'r', encoding='utf-8').read()

# 1. Replace REPORT_SECTION_TITLES
old_pattern = r'REPORT_SECTION_TITLES = \[.*?\]'
new_titles = '''REPORT_SECTION_TITLES = [
    "\u4e00\u3001\u91cd\u8981\u514d\u8d23\u58f0\u660e",
    "\u4e8c\u3001\u6848\u4ef6\u521d\u6b65\u5224\u65ad",
    "\u4e09\u3001\u7528\u6237\u76ee\u6807\u62c6\u89e3",
    "\u56db\u3001\u4e89\u8bae\u7126\u70b9",
    "\u4e94\u3001\u68c0\u7d22\u7ed3\u679c\u5206\u7c7b\u6458\u8981",
    "\u516d\u3001\u7c7b\u6848\u94fe\u63a5",
    "\u4e03\u3001\u6cd5\u5f8b\u4f9d\u636e\u4e0e\u653f\u7b56\u4f9d\u636e",
    "\u516b\u3001\u5904\u7406\u601d\u8def",
    "\u4e5d\u3001\u8bc1\u636e\u8865\u5f3a\u6e05\u5355",
    "\u5341\u3001\u8c08\u5224\u4e0e\u4ef2\u88c1/\u8bc9\u8bbc\u8def\u5f84",
    "\u5341\u4e00\u3001\u4e3b\u8981\u98ce\u9669",
    "\u5341\u4e8c\u3001\u590d\u6838\u72b6\u6001",
    "\u5341\u4e09\u3001\u5f15\u7528\u94fe\u63a5\u6c47\u603b",
    "\u5341\u56db\u3001\u4e0b\u4e00\u6b65\u884c\u52a8\u6e05\u5355",
]'''
src = re.sub(old_pattern, new_titles, src, flags=re.DOTALL)
print("1. REPORT_SECTION_TITLES replaced")

# 2. Insert new constants before REPORT_SECTION_TITLES
insert_block = '''
NO_CASE_LINK_NOTICE = (
    "\u7cfb\u7edf\u672a\u627e\u5230\u53ef\u6838\u9a8c\u7c7b\u6848\u94fe\u63a5\uff0c\u56e0\u6b64\u672c\u62a5\u544a\u4e0d\u63d0\u4f9b\u6848\u4f8b\u652f\u6301\u578b\u7ed3\u8bba\u3002"
    "\u4ee5\u4e0b\u4ec5\u4e3a\u6cd5\u5f8b\u4f9d\u636e\u3001\u653f\u7b56\u4f9d\u636e\u548c\u4e00\u822c\u5904\u7406\u601d\u8def\u3002"
)

REVIEW_NOT_ENABLED_NOTICE = "\u72ec\u7acb\u6cd5\u5f8b\u590d\u6838\u6a21\u578b\u672a\u542f\u7528\uff0c\u672c\u62a5\u544a\u672a\u7ecf\u8fc7\u7b2c\u4e8c\u6cd5\u5f8b\u6a21\u578b\u590d\u6838\u3002"

# -- result_type classification --
RESULT_TYPE_CASE = {"case", "guiding_case", "typical_case", "judgment"}
RESULT_TYPE_LEGAL_BASIS = {"judicial_interpretation", "policy", "statute"}
RESULT_TYPE_OTHER = {"article", "unknown"}


def classify_result_type(title: str, snippet: str = "", extracted_text: str = "") -> str:
    combined = f"{title} {snippet} {extracted_text}"
    for kw in ["\u53f8\u6cd5\u89e3\u91ca", "\u89e3\u91ca\uff08\u4e00", "\u89e3\u91ca\uff08\u4e8c", "\u89e3\u91ca\uff08\u4e09", "\u89e3\u91ca\uff08\u56db", "\u6700\u9ad8\u6cd5\u91ca", "\u6700\u9ad8\u68c0\u91ca", "\u6cd5\u91ca"]:
        if kw in combined:
            return "judicial_interpretation"
    if "\u6307\u5bfc\u6027\u6848\u4f8b" in combined:
        return "guiding_case"
    if "\u5178\u578b\u6848\u4f8b" in combined:
        return "typical_case"
    for kw in ["\u88c1\u5224\u8981\u65e8", "\u57fa\u672c\u6848\u60c5", "\u88c1\u5224\u7406\u7531", "\u4eba\u6c11\u6cd5\u9662", "\u5224\u51b3\u4e66", "\u88c1\u5b9a\u4e66", "\u6848\u53f7"]:
        if kw in combined:
            return "judgment"
    for kw in ["\u610f\u89c1", "\u901a\u77e5", "\u529e\u6cd5", "\u89c4\u5b9a", "\u6761\u4f8b", "\u5b9e\u65bd\u7ec6\u5219"]:
        if kw in title and not any(ck in combined for ck in ["\u88c1\u5224\u8981\u65e8", "\u5224\u51b3\u4e66", "\u6848\u53f7"]):
            return "policy"
    for kw in ["\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd", "\u6c11\u6cd5\u5178", "\u5211\u6cd5", "\u52b3\u52a8\u6cd5", "\u52b3\u52a8\u5408\u540c\u6cd5", "\u793e\u4f1a\u4fdd\u9669\u6cd5", "\u4f4f\u623f\u516c\u79ef\u91d1\u6761\u4f8b"]:
        if kw in title:
            return "statute"
    return "unknown"


# -- labor dispute detection --
LABOR_DISPUTE_KEYWORDS = [
    "\u52b3\u52a8\u5408\u540c", "\u5458\u5de5", "\u8f9e\u9000", "\u89e3\u9664\u52b3\u52a8\u5173\u7cfb", "\u7ecf\u6d4e\u8865\u507f",
    "\u8d54\u507f\u91d1", "\u5de5\u8d44", "\u516c\u79ef\u91d1", "\u793e\u4fdd", "\u4ef2\u88c1", "\u79bb\u804c", "\u5165\u804c",
    "\u52b3\u52a8\u5173\u7cfb", "\u52b3\u52a8\u62a5\u916c", "\u52a0\u73ed\u8d39", "\u5e74\u7ec8\u5956", "\u63d0\u6210", "\u8865\u7f34",
    "\u534f\u5546\u89e3\u9664", "\u8fdd\u6cd5\u89e3\u9664", "\u89e3\u9664\u534f\u8bae", "\u8865\u507f\u6b3e", "\u79bb\u804c\u534f\u8bae",
]


def is_labor_dispute(case_detail: str) -> bool:
    score = sum(1 for kw in LABOR_DISPUTE_KEYWORDS if kw in case_detail)
    return score >= 3
'''

if 'NO_CASE_LINK_NOTICE' not in src:
    idx = src.find('REPORT_SECTION_TITLES')
    src = src[:idx] + insert_block + '\n' + src[idx:]
    print("2. New constants inserted")
else:
    print("2. Constants already exist")

open(path, 'w', encoding='utf-8').write(src)
print("3. Done - file saved")
