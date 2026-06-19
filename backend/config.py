"""
统一配置中心 —— 从 backend/.env 加载所有配置项

所有模块统一通过此文件读取配置，确保：
1. .env 路径使用绝对路径
2. 默认 Provider 为 tavily
3. 不会误读 .env.example
"""

from pathlib import Path
import os
import sys

from dotenv import load_dotenv

# ── .env 绝对路径加载 ──────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    # 严重错误：缺少 .env 文件
    print(f"[config] FATAL: 未找到 .env 文件: {ENV_PATH}")
    print("[config] 请复制 .env.example 为 .env 并填入配置")
    sys.exit(1)

load_dotenv(ENV_PATH, override=True)

# ── DeepSeek ──────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_REASONING_EFFORT = os.getenv("DEEPSEEK_REASONING_EFFORT", "max")
DEEPSEEK_TIMEOUT_SECONDS = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "90"))
KEYWORD_GENERATION_TIMEOUT_SECONDS = int(os.getenv("KEYWORD_GENERATION_TIMEOUT_SECONDS", "90"))
DEEPSEEK_KEYWORD_MAX_TOKENS = int(os.getenv("DEEPSEEK_KEYWORD_MAX_TOKENS", "4096"))
DEEPSEEK_LINK_JUDGE_MAX_TOKENS = int(os.getenv("DEEPSEEK_LINK_JUDGE_MAX_TOKENS", "2048"))
DEEPSEEK_ANALYSIS_MAX_TOKENS = int(os.getenv("DEEPSEEK_ANALYSIS_MAX_TOKENS", "4000"))

# ── 阶段超时保护 ──────────────────────────────────
LINK_JUDGE_TOTAL_TIMEOUT_SECONDS = int(os.getenv("LINK_JUDGE_TOTAL_TIMEOUT_SECONDS", "360"))
REPORT_GENERATION_TIMEOUT_SECONDS = int(os.getenv("REPORT_GENERATION_TIMEOUT_SECONDS", "240"))
WORD_EXPORT_TIMEOUT_SECONDS = int(os.getenv("WORD_EXPORT_TIMEOUT_SECONDS", "60"))

# ── CORS ──────────────────────────────────────────────
DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", DEFAULT_CORS)
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()]

# ── 运行环境 ──────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
IS_DEVELOPMENT = APP_ENV == "development"

# ── 访问令牌 ──────────────────────────────────────────
APP_ACCESS_TOKEN = os.getenv("APP_ACCESS_TOKEN", "").strip()

# 生产模式安全检查：不允许 token 为空
if IS_PRODUCTION and not APP_ACCESS_TOKEN:
    print("=" * 60)
    print("[config] ⚠️  高危警告：APP_ENV=production 但 APP_ACCESS_TOKEN 为空！")
    print("[config] 外部用户可在未认证情况下调用所有 API。")
    print("[config] 请在 backend/.env 中设置强随机 APP_ACCESS_TOKEN。")
    print("[config] 如果确实不需要令牌保护，请设置 APP_ENV=development。")
    print("=" * 60)
    # 生产模式 + 无 token → 拒绝启动
    sys.exit(1)

# 允许免 token 访问的路径前缀
PUBLIC_PATHS = ["/api/health", "/api/config/runtime", "/api/model-status"]

# ── 在线搜索 ──────────────────────────────────────────
ONLINE_SEARCH_ENABLED = os.getenv("ONLINE_SEARCH_ENABLED", "true").lower() == "true"
CASE_SEARCH_MODE = os.getenv("CASE_SEARCH_MODE", "online_index")
ONLINE_SEARCH_PROVIDER = os.getenv("ONLINE_SEARCH_PROVIDER", "tavily").lower()

# Tavily (推荐)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# Google CSE (备选)
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

# Bing (Legacy，不推荐)
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
BING_CUSTOM_CONFIG_ID = os.getenv("BING_CUSTOM_CONFIG_ID", "")
BING_SEARCH_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", "")

# 检索参数（标准模式默认值）
MAX_SEARCH_KEYWORDS_PER_GOAL = int(os.getenv("MAX_SEARCH_KEYWORDS_PER_GOAL", "5"))
MAX_SEARCH_RESULTS_PER_KEYWORD = int(os.getenv("MAX_SEARCH_RESULTS_PER_KEYWORD", "8"))
MAX_LINKS_TO_JUDGE = int(os.getenv("MAX_LINKS_TO_JUDGE", "15"))
MAX_LINKS_TO_USE = int(os.getenv("MAX_LINKS_TO_USE", "5"))

# AI 判断链接性能优化
LINK_JUDGE_BATCH_SIZE = int(os.getenv("LINK_JUDGE_BATCH_SIZE", "2"))
LINK_JUDGE_TIMEOUT_SECONDS = int(os.getenv("LINK_JUDGE_TIMEOUT_SECONDS", "90"))
LINK_JUDGE_MAX_TITLE_CHARS = int(os.getenv("LINK_JUDGE_MAX_TITLE_CHARS", "120"))
LINK_JUDGE_MAX_SNIPPET_CHARS = int(os.getenv("LINK_JUDGE_MAX_SNIPPET_CHARS", "300"))
LINK_JUDGE_USE_PAGE_CONTENT = os.getenv("LINK_JUDGE_USE_PAGE_CONTENT", "false").lower() == "true"
LINK_JUDGE_SKIP_PDF_CONTENT = os.getenv("LINK_JUDGE_SKIP_PDF_CONTENT", "true").lower() == "true"
LINK_JUDGE_QUICK_PASS_TOP_N = int(os.getenv("LINK_JUDGE_QUICK_PASS_TOP_N", "5"))
LINK_JUDGE_DEEP_PASS_TOP_N = int(os.getenv("LINK_JUDGE_DEEP_PASS_TOP_N", "3"))
SKIP_PDF_DIRECT_EXTRACT = LINK_JUDGE_SKIP_PDF_CONTENT

# AI 失败模式：strict=AI 失败则停止任务，lenient=允许规则 fallback
AI_FAILURE_MODE = os.getenv("AI_FAILURE_MODE", "strict").lower()
AI_KEYWORD_REQUIRED = os.getenv("AI_KEYWORD_REQUIRED", "true").lower() == "true"
AI_LINK_JUDGE_REQUIRED = os.getenv("AI_LINK_JUDGE_REQUIRED", "true").lower() == "true"
ENABLE_RULE_KEYWORD_FALLBACK = os.getenv("ENABLE_RULE_KEYWORD_FALLBACK", "false").lower() == "true"
ENABLE_RULE_LINK_JUDGE_FALLBACK = os.getenv("ENABLE_RULE_LINK_JUDGE_FALLBACK", "false").lower() == "true"

def is_strict_mode() -> bool:
    return AI_FAILURE_MODE == "strict"

# ── 输出目录 ──────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")

# ── OCR ───────────────────────────────────────────────
ENABLE_OCR = os.getenv("ENABLE_OCR", "false").lower() == "true"
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "none").lower()
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "ch")
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "20"))
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_SAVE_DEBUG_IMAGES = os.getenv("OCR_SAVE_DEBUG_IMAGES", "false").lower() == "true"

# ── 本地法律模型 ──────────────────────────────────────
USE_LAWFORMER = os.getenv("USE_LAWFORMER", "false").lower() == "true"
USE_DISC_LAWLLM = os.getenv("USE_DISC_LAWLLM", "false").lower() == "true"
USE_INTERNLM_LAW = os.getenv("USE_INTERNLM_LAW", "false").lower() == "true"

# ── 工具函数 ──────────────────────────────────────────

def has_real_value(name: str) -> bool:
    """检查环境变量是否有真实值（非空且非占位符）"""
    value = os.getenv(name, "")
    if value is None:
        return False
    value = str(value).strip()
    if not value:
        return False
    lowered = value.lower()
    invalid = {"your_api_key", "your_tavily_api_key", "your_key", "none", "null", "false", "undefined"}
    if lowered in invalid or value.startswith("your_"):
        return False
    return True


def online_provider_ready() -> bool:
    """检查当前在线搜索 Provider 是否已就绪"""
    if not ONLINE_SEARCH_ENABLED:
        return False
    if ONLINE_SEARCH_PROVIDER == "tavily":
        return bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith("your_"))
    if ONLINE_SEARCH_PROVIDER == "google_cse":
        return bool(GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX and not GOOGLE_CSE_API_KEY.startswith("your_"))
    # Bing (legacy)
    return bool(BING_SEARCH_API_KEY and not BING_SEARCH_API_KEY.startswith("your_"))


def get_provider_status() -> dict:
    """获取 Provider 状态（安全，不含完整 Key）"""
    provider = ONLINE_SEARCH_PROVIDER
    api_key_configured = False
    key_masked = ""

    if provider == "tavily":
        api_key_configured = bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith("your_"))
        if api_key_configured and TAVILY_API_KEY:
            key_masked = TAVILY_API_KEY[:8] + "****" + TAVILY_API_KEY[-4:] if len(TAVILY_API_KEY) > 12 else "****"
    elif provider == "google_cse":
        api_key_configured = bool(GOOGLE_CSE_API_KEY and not GOOGLE_CSE_API_KEY.startswith("your_"))
        if api_key_configured and GOOGLE_CSE_API_KEY:
            key_masked = GOOGLE_CSE_API_KEY[:8] + "****" + GOOGLE_CSE_API_KEY[-4:] if len(GOOGLE_CSE_API_KEY) > 12 else "****"
    elif provider == "bing":
        api_key_configured = bool(BING_SEARCH_API_KEY and not BING_SEARCH_API_KEY.startswith("your_"))
        if api_key_configured and BING_SEARCH_API_KEY:
            key_masked = BING_SEARCH_API_KEY[:4] + "****" + BING_SEARCH_API_KEY[-4:] if len(BING_SEARCH_API_KEY) > 8 else "****"

    return {
        "provider": provider,
        "enabled": ONLINE_SEARCH_ENABLED,
        "api_key_configured": api_key_configured,
        "ready": ONLINE_SEARCH_ENABLED and api_key_configured,
        "message": (
            f"{provider.title()} 在线搜索已配置"
            if (ONLINE_SEARCH_ENABLED and api_key_configured)
            else f"未配置 {provider.title()} API Key，无法真实在线检索"
        ),
    }


# ── 启动安全日志（不打印完整 Key） ───────────────────

def print_startup_config():
    """启动时安全打印配置摘要"""
    env_exists = ENV_PATH.exists()
    deepseek_ok = bool(DEEPSEEK_API_KEY and not DEEPSEEK_API_KEY.startswith("your_"))
    key_masked = DEEPSEEK_API_KEY[:8] + "****" + DEEPSEEK_API_KEY[-4:] if len(DEEPSEEK_API_KEY) > 12 else ("****" if DEEPSEEK_API_KEY else "(empty)")
    print(f"[config] env_path={ENV_PATH}")
    print(f"[config] env_exists={env_exists}")
    print(f"[config] app_env={APP_ENV}")
    print(f"[config] access_token_configured={bool(APP_ACCESS_TOKEN)}")
    print(f"[config] deepseek_key_configured={deepseek_ok}")
    print(f"[config] deepseek_key_masked={key_masked}")
    print(f"[config] deepseek_model={DEEPSEEK_MODEL}")
    print(f"[config] deepseek_base_url={DEEPSEEK_BASE_URL}")
    print(f"[online_search] enabled={ONLINE_SEARCH_ENABLED}")
    print(f"[online_search] case_search_mode={CASE_SEARCH_MODE}")
    print(f"[online_search] provider={ONLINE_SEARCH_PROVIDER}")

    if ONLINE_SEARCH_PROVIDER == "tavily":
        api_ok = bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith("your_"))
        key_len = len(TAVILY_API_KEY) if TAVILY_API_KEY else 0
        masked = TAVILY_API_KEY[:8] + "****" + TAVILY_API_KEY[-4:] if len(TAVILY_API_KEY) > 12 else ("****" if TAVILY_API_KEY else "(empty)")
        print(f"[online_search] tavily_key_length={key_len}")
        print(f"[online_search] tavily_key_configured={api_ok}")
        print(f"[online_search] tavily_key_masked={masked}")
    elif ONLINE_SEARCH_PROVIDER == "google_cse":
        print(f"[online_search] google_cse_key_configured={has_real_value('GOOGLE_CSE_API_KEY')}")
    elif ONLINE_SEARCH_PROVIDER == "bing":
        print(f"[online_search] bing_key_configured={has_real_value('BING_SEARCH_API_KEY')}")
