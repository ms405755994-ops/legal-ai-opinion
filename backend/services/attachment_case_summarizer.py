"""附件案件整理器 —— 调用 DeepSeek 将附件原文整理成结构化案件详情"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """你是案件材料整理助手。你的任务是从用户上传的附件文字中提取案件事实，并整理成"案件详情"输入内容。

要求：
1. 只整理事实，不输出正式法律意见。
2. 不编造附件中不存在的事实。
3. 不编造证据。
4. 不编造日期、金额、案号、法院。
5. 对不确定内容标记为"附件中未明确"。
6. 按时间线、当事人关系、证据、争议焦点整理。
7. 输出内容要适合直接填入案件详情输入框。
8. 如果附件内容过短或无法判断案件事实，明确提示需要用户补充。"""

OUTPUT_FORMAT = """请按以下格式输出案件详情（不要输出其他内容）：

【案件类型】
如：劳动争议 / 合同纠纷 / 买卖合同 / 服务合同 / 侵权纠纷 等

【当事人关系】
甲方/乙方/公司/员工/买方/卖方等关系

【时间线】
按时间顺序整理关键事件

【核心事实】
整理案件发生经过

【已有证据】
列出附件中出现的合同、付款、聊天记录、通知、凭证等

【争议焦点】
列出双方争议点

【对方主张】
如附件中能看出对方主张，则整理；如无，标注"附件中未明确"

【我方目标相关事实】
提取对用户希望结果有帮助的事实；如用户未提供期望目标，标注"待用户补充期望目标后进一步分析"

【需要补充的信息】
列出附件中缺失但后续分析需要的信息"""


def summarize_case_from_attachments(
    raw_text: str,
    existing_case_detail: str = "",
) -> str:
    """调用 DeepSeek 将附件原文整理成结构化案件详情。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return _mock_summarize(raw_text, existing_case_detail)

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    user_prompt = f"""请根据以下附件提取文字，整理成案件详情输入内容：

=== 附件原文 ===
{raw_text[:12000]}

=== 已有案件详情（如有） ===
{existing_case_detail if existing_case_detail else "（无已有内容）"}

{OUTPUT_FORMAT}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            resp = client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 8192,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return (
            f"⚠️ AI 整理失败（{exc}），以下为附件原文与已有内容的拼接：\n\n"
            f"=== 附件原文 ===\n{raw_text[:3000]}\n\n"
            f"=== 已有内容 ===\n{existing_case_detail}"
        )


def _mock_summarize(raw_text: str, existing_case_detail: str) -> str:
    """无 API Key 时的模拟整理"""
    prefix = "⚠️ DeepSeek API Key 未配置，以下为附件原文与已有内容的简单拼接：\n\n"
    parts = []
    if existing_case_detail:
        parts.append(f"【已有案件详情】\n{existing_case_detail}")
    parts.append(f"【附件原文】\n{raw_text[:5000]}")
    return prefix + "\n\n---\n\n".join(parts)
