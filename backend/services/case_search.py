"""
案例检索模块 —— 第一版使用模拟数据，但预留真实数据源检索接口
"""

import hashlib
import time
from typing import List, Dict, Optional

from services.source_manager import get_source_manager, SourceItem


# ── 模拟案例库（仅供开发调试） ──────────────────────────
# ⚠️ 所有模拟案例均标记 is_mock=True，不会伪装成真实案例

MOCK_CASES: List[Dict] = [
    {
        "title": "张某与某电商平台网络购物合同纠纷案",
        "case_no": "（2024）京 0491 民初 12345 号",
        "court": "北京互联网法院",
        "judgment_date": "2024-03-15",
        "issue": "网购商品质量问题与退货退款",
        "holding": "经营者提供的商品不符合质量要求的，消费者可以依照国家规定、当事人约定退货。网络购物中，消费者享有七日无理由退货权利。",
        "url": "https://wenshu.court.gov.cn（模拟链接-不可点击）",
        "source_name": "中国裁判文书网",
        "is_mock": True,
    },
    {
        "title": "李某诉某房地产开发公司商品房买卖合同纠纷案",
        "case_no": "（2023）最高法民终 5678 号",
        "court": "最高人民法院",
        "judgment_date": "2023-11-20",
        "issue": "商品房买卖合同解除与损失赔偿",
        "holding": "因出卖人违约导致合同目的无法实现的，买受人有权解除合同并要求赔偿损失。违约损失赔偿额应相当于因违约所造成的损失，包括合同履行后可以获得的利益。",
        "url": "https://wenshu.court.gov.cn（模拟链接-不可点击）",
        "source_name": "中国裁判文书网",
        "is_mock": True,
    },
    {
        "title": "王某与某保险公司人身保险合同纠纷案",
        "case_no": "（2024）沪 0115 民初 23456 号",
        "court": "上海市浦东新区人民法院",
        "judgment_date": "2024-01-10",
        "issue": "保险公司理赔义务与违约责任",
        "holding": "保险合同成立后，投保人按照约定交付保险费，保险人按照约定的时间开始承担保险责任。保险人未及时履行赔偿或者给付保险金义务的，除支付保险金外，应当赔偿被保险人或者受益人因此受到的损失。",
        "url": "https://rmfyalk.court.gov.cn（模拟链接-不可点击）",
        "source_name": "人民法院案例库",
        "is_mock": True,
    },
    {
        "title": "某科技公司诉某软件公司技术服务合同纠纷案",
        "case_no": "（2024）粤 03 民终 34567 号",
        "court": "广东省深圳市中级人民法院",
        "judgment_date": "2024-05-08",
        "issue": "技术服务合同履行与违约责任",
        "holding": "技术服务提供方未按约定完成服务内容的，委托方有权要求继续履行、采取补救措施或赔偿损失。合同中对违约金有约定的从约定，但不得超过实际损失的30%。",
        "url": "https://wenshu.court.gov.cn（模拟链接-不可点击）",
        "source_name": "中国裁判文书网",
        "is_mock": True,
    },
    {
        "title": "赵某与某培训机构教育培训合同纠纷案",
        "case_no": "（2024）京 0105 民初 45678 号",
        "court": "北京市朝阳区人民法院",
        "judgment_date": "2024-06-20",
        "issue": "教育培训合同退费纠纷",
        "holding": "教育培训机构未按约定提供服务的，消费者有权要求退还相应费用。预付费消费模式中，经营者停业、歇业且未提前告知的，消费者有权要求返还预付款。",
        "url": "https://rmfyalk.court.gov.cn（模拟链接-不可点击）",
        "source_name": "人民法院案例库",
        "is_mock": True,
    },
    {
        "title": "某物流公司与某商贸公司运输合同纠纷案",
        "case_no": "（2023）苏 05 民终 56789 号",
        "court": "江苏省苏州市中级人民法院",
        "judgment_date": "2023-09-12",
        "issue": "货物运输毁损赔偿与责任认定",
        "holding": "承运人对运输过程中货物的毁损、灭失承担赔偿责任，但承运人证明货物的毁损、灭失是因不可抗力、货物本身的自然性质或者合理损耗以及托运人、收货人的过错造成的，不承担赔偿责任。",
        "url": "https://wenshu.court.gov.cn（模拟链接-不可点击）",
        "source_name": "中国裁判文书网",
        "is_mock": True,
    },
]


class CaseSearchEngine:
    """案例检索引擎"""

    def __init__(self) -> None:
        self.source_mgr = get_source_manager()

    def search(self, keywords: List[str], top_k: int = 10) -> List[Dict]:
        """
        根据关键词检索案例

        第一版：从模拟案例库中按关键词匹配。
        后续版本：从启用的数据源中真实检索（预留接口）。
        """
        # ── 模拟检索 ──
        mock_results = self._mock_search(keywords, top_k)
        
        # ── 真实数据源检索（预留接口） ──
        # enabled_sources = self.source_mgr.list_enabled()
        # real_results = []
        # for source in enabled_sources:
        #     try:
        #         results = self._search_real_source(source, keywords, top_k)
        #         real_results.extend(results)
        #     except Exception:
        #         pass
        # if real_results:
        #     return real_results[:top_k]

        return mock_results[:top_k]

    def _mock_search(self, keywords: List[str], top_k: int) -> List[Dict]:
        """模拟检索：按关键词简单匹配"""
        scored = []
        for case in MOCK_CASES:
            score = 0
            text = f"{case['title']} {case['issue']} {case['holding']}"
            for kw in keywords:
                if kw in text:
                    score += 1
            if score > 0:
                scored.append((score, case))
        # 按匹配度降序
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored][:top_k] if scored else MOCK_CASES[:top_k]

    # ── 真实检索接口（预留，后续实现） ──

    def _search_real_source(self, source: SourceItem, keywords: List[str],
                            top_k: int) -> List[Dict]:
        """
        从真实数据源检索案例（预留接口）

        后续实现计划：
        - 人民法院案例库：通过官方 API 或爬虫检索
        - 中国裁判文书网：通过官方 API 检索
        - 北大法宝 / 威科先行：通过商业 API 检索

        当前返回空列表。
        """
        # TODO: 实现真实检索逻辑
        return []


# 便捷函数
def get_case_search_engine() -> CaseSearchEngine:
    return CaseSearchEngine()
