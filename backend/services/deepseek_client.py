import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from legal_models.mock.mock_legal_model import mock_decompose_case, mock_search_keywords
from services.prompt_templates import DEEPSEEK_SYSTEM_PROMPT


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        self.reasoning_effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "max")
        self.timeout_seconds = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def decompose_case(self, case_detail: str, goals: List[str]) -> Dict[str, Any]:
        fallback = mock_decompose_case(case_detail, goals)
        if not self.enabled:
            return fallback

        prompt = f"""请对案件进行结构化拆解，只输出 JSON，不要输出 Markdown。

案件详情：
{case_detail}

用户目标：
{goals}

JSON 字段：
- cause_of_action_candidates: 案由候选数组
- legal_relations: 法律关系数组
- dispute_focus: 争议焦点数组
- evidence_checklist: 证据清单数组
- opposing_defenses: 对方可能抗辩数组
- goal_paths: 每个目标的法律路径数组，每项包含 goal、legal_path、supportability
"""
        data = self._chat_json(prompt, fallback)
        return data if isinstance(data, dict) else fallback

    def generate_search_keywords(self, case_detail: str, goals: List[str], decompose_result: Dict) -> Dict:
        fallback = mock_search_keywords(case_detail, goals, decompose_result)
        if not self.enabled:
            return fallback

        prompt = f"""请基于案件拆解结果生成类案检索关键词，只输出 JSON。

案件详情：
{case_detail}

用户目标：
{goals}

案件拆解：
{json.dumps(decompose_result, ensure_ascii=False)}

JSON 字段：
- keyword_groups: 数组，每项包含 goal、cause_keywords、issue_keywords、holding_keywords、winning_direction_keywords
- global_keywords: 全局关键词数组
"""
        data = self._chat_json(prompt, fallback)
        return data if isinstance(data, dict) else fallback

    def _chat_json(self, user_prompt: str, fallback: Dict) -> Dict:
        raw = self._chat(
            [
                {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT + "\n请严格输出 JSON。"},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        parsed = self._extract_json(raw)
        return parsed if isinstance(parsed, dict) else fallback

    def _chat(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                resp = client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                status_code = resp.status_code
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

                # ── 响应诊断（安全，不含 Key） ──
                choices = data.get("choices", [])
                finish_reason = choices[0].get("finish_reason", "?") if choices else "?"
                usage = data.get("usage", {})
                msg = choices[0].get("message", {}) if choices else {}
                content = msg.get("content", "") or ""
                reasoning = msg.get("reasoning_content", "") or ""

                # DeepSeek 有时将最终回复放在 reasoning_content 中，content 为空
                if not content and reasoning:
                    content = reasoning

                error_obj = data.get("error", None)

                # 诊断日志
                diag = (
                    f"deepseek_response status={status_code} "
                    f"finish_reason={finish_reason} "
                    f"choices_count={len(choices)} "
                    f"content_length={len(content)} "
                    f"reasoning_length={len(reasoning)} "
                    f"prompt_tokens={usage.get('prompt_tokens', '?')} "
                    f"completion_tokens={usage.get('completion_tokens', '?')} "
                    f"total_tokens={usage.get('total_tokens', '?')}"
                )
                if error_obj:
                    diag += f" error_type={error_obj.get('type', '?')} error_msg={str(error_obj.get('message', ''))[:200]}"
                if not content and reasoning:
                    diag += " note=content_empty_reasoning_present"

                # Print to stderr for startup log, not stored in tracker
                import sys
                print(f"[deepseek] {diag}", file=sys.stderr, flush=True)

                resp.raise_for_status()
                return content

        except Exception:
            return ""

    def _chat_with_diagnostics(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> dict:
        """
        增强版 _chat，返回 { content, diagnostics } 用于调试。
        不影响现有 _chat() 行为。
        """
        result = {"content": "", "diagnostics": {
            "status_code": 0, "choices_count": 0, "finish_reason": "?",
            "content_length": 0, "reasoning_length": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "message_keys": [], "error_type": None, "error_message": None,
        }}

        payload: Dict[str, Any] = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                resp = client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                d = result["diagnostics"]
                d["status_code"] = resp.status_code
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

                choices = data.get("choices", [])
                usage = data.get("usage", {})
                error_obj = data.get("error")

                d["choices_count"] = len(choices)
                d["finish_reason"] = choices[0].get("finish_reason", "?") if choices else "?"
                d["prompt_tokens"] = usage.get("prompt_tokens", 0)
                d["completion_tokens"] = usage.get("completion_tokens", 0)
                d["total_tokens"] = usage.get("total_tokens", 0)

                if choices:
                    msg = choices[0].get("message", {})
                    d["content_length"] = len(msg.get("content", "") or "")
                    d["reasoning_length"] = len(msg.get("reasoning_content", "") or "")
                    d["message_keys"] = list(msg.keys())
                    content_text = msg.get("content", "") or ""
                    reasoning_text = msg.get("reasoning_content", "") or ""
                    # DeepSeek 有时将最终回复放在 reasoning_content 中
                    result["content"] = content_text if content_text else reasoning_text

                if error_obj:
                    d["error_type"] = error_obj.get("type", "?")
                    d["error_message"] = str(error_obj.get("message", ""))[:300]

                resp.raise_for_status()
                return result
        except Exception as exc:
            result["diagnostics"]["error_type"] = "exception"
            result["diagnostics"]["error_message"] = str(exc)[:300]
            return result

    @staticmethod
    def _extract_json(raw: str) -> Optional[Any]:
        from utils.robust_json_parser import parse_deepseek_output
        parsed, method, diag = parse_deepseek_output(raw)
        if parsed is not None:
            return parsed
        return None


_client: Optional[DeepSeekClient] = None


def get_deepseek_client() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client
