"""
文本工具 —— 关键词分词、目标拆分、Markdown 转换
"""
import re
from typing import List


def split_goals(goals_raw: str) -> List[str]:
    """拆分用户希望结果（按换行、分号、序号拆分）"""
    if not goals_raw or not goals_raw.strip():
        return []
    # 先按换行分
    lines = [line.strip() for line in goals_raw.split('\n') if line.strip()]
    goals = []
    for line in lines:
        # 去掉序号前缀如 "1." "1、" "(1)"
        cleaned = re.sub(r'^[\s]*[\d]+[\.\、\)）]\s*', '', line).strip()
        if cleaned:
            goals.append(cleaned)
    return goals if goals else [goals_raw.strip()]


def keyword_tokens(text: str) -> List[str]:
    """将文本分词为关键词 token 列表"""
    if not text:
        return []
    # 简单按空格和常见分隔符分词
    tokens = re.split(r'[\s,，。；;、\u3000]+', text)
    return [t.strip() for t in tokens if len(t.strip()) >= 2]


def overlap_score(tokens1: List[str], tokens2: List[str]) -> float:
    """计算两个 token 列表的重叠得分 (0.0 ~ 1.0)"""
    if not tokens1 or not tokens2:
        return 0.0
    set1 = set(tokens1)
    set2 = set(tokens2)
    intersection = set1 & set2
    union = set1 | set2
    if not union:
        return 0.0
    return len(intersection) / len(union)


def markdown_to_html(markdown: str) -> str:
    """简单的 Markdown 转 HTML（基础支持）"""
    if not markdown:
        return ""
    # 这里只做基础转换，主要依赖前端 marked.js
    html = markdown
    # 粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # 斜体
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # 换行
    html = html.replace('\n\n', '</p><p>').replace('\n', '<br>')
    html = f'<p>{html}</p>'
    return html
