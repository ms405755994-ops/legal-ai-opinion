import os
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import (
    APP_ACCESS_TOKEN,
    APP_ENV,
    CORS_ORIGINS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    IS_DEVELOPMENT,
    IS_PRODUCTION,
    ONLINE_SEARCH_PROVIDER,
    PUBLIC_PATHS,
    get_provider_status,
    has_real_value,
    online_provider_ready,
    print_startup_config,
    AI_FAILURE_MODE,
    AI_KEYWORD_REQUIRED,
    AI_LINK_JUDGE_REQUIRED,
    ENABLE_RULE_KEYWORD_FALLBACK,
    ENABLE_RULE_LINK_JUDGE_FALLBACK,
)
from schemas.models import (
    AnalyzeCancelResponse,
    AnalyzeProgressResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStartRequest,
    AnalyzeStartResponse,
    AttachmentExtractResponse,
    AttachmentFileResult,
    CaseLinkUpdate,
    CaseRankRequest,
    CaseRankResponse,
    CaseReference,
    CaseSearchRequest,
    CaseSearchResponse,
    ExportDocxRequest,
    ExportDocxResponse,
    HealthResponse,
    LegalReviewRequest,
    ModelStatusEntry,
    OnlineCollectRequest,
    OnlineJudgeLinksRequest,
    OnlineKeywordRequest,
    OnlineSearchRequest,
    OnlineSourceUpdate,
    ReviewResult,
    SourceCreate,
    SourceItem,
    SourceUpdate,
)
from services.case_ranker import get_case_ranker
from services.case_search import get_case_search_engine
from services.legal_reviewer import review_legal_analysis
from services.case_link_store import get_case_link_store
from services.online_search_client import get_online_search_client
from services.online_search_workflow import collect_online_links, judge_links, online_sources, preview_keywords, search_online_index
from services.official_source_filter import update_online_source
from services.report_generator import get_report_generator
from services.source_manager import get_source_manager
from services.workflow import run_analysis
from services.workflow_with_progress import run_analysis_with_progress, _JobCancelledError
from services.analyze_job_manager import get_job_manager, ProgressTracker
from services.attachment_text_extractor import extract_text
from services.attachment_case_summarizer import summarize_case_from_attachments
from utils.text_utils import split_goals
from utils.upload_utils import cleanup_temp_files, ensure_upload_dir, safe_filename, validate_file


app = FastAPI(
    title="legal-ai-opinion",
    description="AI 类案检索助手，本系统不构成正式法律意见。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Token 鉴权中间件 ─────────────────────────────────
@app.middleware("http")
async def token_auth_middleware(request: Request, call_next):
    # 公开路径免 token
    path = request.url.path
    if any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    # OPTIONS 预检请求免 token
    if request.method == "OPTIONS":
        return await call_next(request)

    # 开发模式且未配置 token 时跳过验证
    if IS_DEVELOPMENT and not APP_ACCESS_TOKEN:
        return await call_next(request)

    # 验证 Bearer Token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != APP_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="未提供有效的访问令牌")

    return await call_next(request)


_analysis_store: Dict[str, dict] = {}

# ── 启动安全日志 ────────────────────────────────────
print_startup_config()


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="1.0.0",
        model=DEEPSEEK_MODEL,
    )


@app.get("/api/model-status", response_model=Dict[str, ModelStatusEntry])
def model_status() -> Dict[str, ModelStatusEntry]:
    return {
        "deepseek": ModelStatusEntry(
            enabled=has_real_value("DEEPSEEK_API_KEY"),
            mode="api",
            role="主分析模型",
        ),
        "lawformer": ModelStatusEntry(
            enabled=bool(os.getenv("USE_LAWFORMER", "false").lower() == "true"),
            mode=os.getenv("LAWFORMER_MODE", "mock"),
            role="类案相似度排序",
        ),
        "disc_lawllm": ModelStatusEntry(
            enabled=bool(os.getenv("USE_DISC_LAWLLM", "false").lower() == "true"),
            mode=os.getenv("DISC_LAWLLM_MODE", "mock"),
            role="法律复核",
        ),
        "internlm_law": ModelStatusEntry(
            enabled=bool(os.getenv("USE_INTERNLM_LAW", "false").lower() == "true"),
            mode=os.getenv("INTERNLM_LAW_MODE", "mock"),
            role="备用法律复核",
        ),
        "online_search": ModelStatusEntry(
            enabled=online_provider_ready(),
            mode=ONLINE_SEARCH_PROVIDER,
            role="在线索引类案检索",
        ),
    }


@app.get("/api/online-search/provider-status")
def online_provider_status() -> dict:
    """获取在线搜索 Provider 状态（不返回完整 API Key）"""
    return get_provider_status()


@app.get("/api/config/runtime")
def config_runtime() -> dict:
    """返回当前运行时配置（不含密钥）"""
    from pathlib import Path
    env_path = Path(__file__).resolve().parent / ".env"
    return {
        "env_path": str(env_path),
        "env_exists": env_path.exists(),
        "DEEPSEEK_API_KEY_CONFIGURED": bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY.strip()),
        "DEEPSEEK_API_KEY_MASKED": DEEPSEEK_API_KEY[:8] + "****" + DEEPSEEK_API_KEY[-4:] if len(DEEPSEEK_API_KEY) > 12 else "(empty)",
        "DEEPSEEK_MODEL": DEEPSEEK_MODEL,
        "DEEPSEEK_BASE_URL": DEEPSEEK_BASE_URL,
        "AI_FAILURE_MODE": AI_FAILURE_MODE,
        "ENABLE_RULE_KEYWORD_FALLBACK": ENABLE_RULE_KEYWORD_FALLBACK,
        "ONLINE_SEARCH_PROVIDER": ONLINE_SEARCH_PROVIDER,
    }


# ── DeepSeek 诊断接口 ──────────────────────────────

@app.get("/api/deepseek/health")
def deepseek_health() -> dict:
    """检查 DeepSeek 配置和基础连通性"""
    api_key = DEEPSEEK_API_KEY
    configured = bool(api_key and api_key.strip())
    key_masked = api_key[:8] + "****" + api_key[-4:] if len(api_key) > 12 else ("(empty)" if not api_key else "****")
    env_path = Path(__file__).resolve().parent / ".env"

    if not configured:
        return {
            "success": False, "configured": False, "api_key_configured": False,
            "display_model": "DeepSeek V4-Pro", "api_model": DEEPSEEK_MODEL,
            "base_url": DEEPSEEK_BASE_URL, "api_key_masked": key_masked,
            "env_path": str(env_path), "env_exists": env_path.exists(),
        }

    from services.deepseek_client import get_deepseek_client
    llm = get_deepseek_client()
    try:
        result = llm._chat_with_diagnostics([{"role": "user", "content": "回复 OK"}], 0.1, 100)
        d = result["diagnostics"]
        content = result.get("content", "")
        finish = d.get("finish_reason", "?")
        ok = d["status_code"] == 200 and len(content) > 0

        return {
            "success": ok, "configured": True, "api_key_configured": True,
            "display_model": "DeepSeek V4-Pro", "api_model": DEEPSEEK_MODEL,
            "base_url": DEEPSEEK_BASE_URL, "api_key_masked": key_masked,
            "env_path": str(env_path), "env_exists": env_path.exists(),
            "last_check": {"status_code": d["status_code"], "finish_reason": finish,
                           "content_length": d["content_length"],
                           "prompt_tokens": d["prompt_tokens"], "completion_tokens": d["completion_tokens"],
                           "message_keys": d.get("message_keys", [])},
            "last_error": d.get("error_message") if not ok else None,
        }
    except Exception as exc:
        return {
            "success": False, "configured": True, "api_key_configured": True,
            "display_model": "DeepSeek V4-Pro", "api_model": DEEPSEEK_MODEL,
            "base_url": DEEPSEEK_BASE_URL, "api_key_masked": key_masked,
            "env_path": str(env_path), "env_exists": env_path.exists(),
            "last_error": str(exc),
        }


@app.post("/api/deepseek/test-keyword-generation")
def deepseek_test_keywords(request: AnalyzeStartRequest) -> dict:
    """单独测试关键词生成，不触发 Tavily"""
    from services.deepseek_client import get_deepseek_client
    from utils.robust_json_parser import parse_robust_json, get_field
    from utils.text_utils import split_goals
    from config import DEEPSEEK_KEYWORD_MAX_TOKENS, DEEPSEEK_TIMEOUT_SECONDS

    goals = split_goals(request.goals)
    llm = get_deepseek_client()

    prompt = f"""你是法律类案检索关键词生成器。请基于案件详情和希望结果，生成 6-10 个适合搜索公开裁判案例和官方案例库的中文检索关键词。

要求：
1. 每个关键词 4-20 个字。
2. 不要整句复制用户希望结果。
3. 不要输出解释，不要输出 markdown。
4. 只返回严格 JSON，不要任何其他文字。

输出格式：{{"keywords": ["关键词1", "关键词2"]}}

案件详情：{request.case_detail[:3000]}
希望结果：{request.goals}"""

    result = llm._chat_with_diagnostics(
        [{"role": "system", "content": "你是法律检索关键词生成器。只输出 JSON，不做解释。"}, {"role": "user", "content": prompt}],
        0.1, DEEPSEEK_KEYWORD_MAX_TOKENS,
    )
    d = result["diagnostics"]
    raw = result.get("content", "")
    raw_length = len(raw)
    finish = d.get("finish_reason", "?")
    is_truncated = finish == "length"

    parsed, method, diag = parse_robust_json(raw)
    keywords = []
    parse_success = False

    if isinstance(parsed, dict):
        keywords = get_field(parsed, "keywords", [])
        if not keywords and "keywords" in parsed:
            keywords = parsed["keywords"]
        keywords = [str(k).strip() for k in keywords if str(k).strip()]
        parse_success = len(keywords) > 0

    success = raw_length > 0 and parse_success and not is_truncated

    suggestions = []
    if raw_length == 0:
        suggestions = [
            "检查 deepseek_client.py 是否取错字段",
            "检查关键词生成 prompt 是否过长",
            f"检查 max_tokens 是否过小（当前 {DEEPSEEK_KEYWORD_MAX_TOKENS}）",
            "检查 DeepSeek API 是否偶发返回空 content",
            "尝试切换 deepseek-chat / deepseek-reasoner 模型",
        ]
    elif is_truncated:
        suggestions = [
            f"DeepSeek 输出被 max_tokens={DEEPSEEK_KEYWORD_MAX_TOKENS} 截断，请提高 DEEPSEEK_KEYWORD_MAX_TOKENS",
            "或简化 prompt，只要求输出短 JSON",
        ]
    elif not parse_success:
        suggestions = [
            f"解析失败（{method}: {diag.get('error','?')}），检查返回格式",
            "检查是否返回了 markdown 或额外解释文字",
        ]

    return {
        "success": success, "stage": "keyword_generation",
        "raw_length": raw_length, "raw_preview": raw[:400],
        "parse_success": parse_success, "parse_method": method,
        "keyword_count": len(keywords), "keywords": keywords[:15],
        "output_truncated": is_truncated,
        "finish_reason": finish,
        "deepseek_diagnostics": {
            "status_code": d["status_code"], "choices_count": d["choices_count"],
            "finish_reason": finish, "content_length": d["content_length"],
            "reasoning_length": d["reasoning_length"],
            "prompt_tokens": d["prompt_tokens"], "completion_tokens": d["completion_tokens"],
            "total_tokens": d["total_tokens"], "message_keys": d.get("message_keys", []),
            "error_type": d.get("error_type"), "error_message": d.get("error_message"),
        },
        "check_suggestions": suggestions,
    }


@app.post("/api/deepseek/test-link-judge")
def deepseek_test_link_judge(request: dict) -> dict:
    """单独测试链接判断"""
    from services.deepseek_client import get_deepseek_client
    from utils.robust_json_parser import parse_deepseek_output, parse_batch_judgment_results

    case_detail = request.get("case_detail", "")
    goals = request.get("goals", "")
    links = request.get("links", [])[:5]

    if not case_detail or not links:
        return {"success": False, "error": "case_detail 和 links 为必填"}

    llm = get_deepseek_client()
    links_text = ""
    for i, link in enumerate(links, 1):
        links_text += f"链接 {i}: {link.get('title','')} URL: {link.get('url','')}\n摘要: {link.get('snippet','')}\n\n"

    prompt = f"""批量判断这些搜索结果对案件是否有用。只输出 JSON 数组。

案件: {case_detail[:2000]}
目标: {goals}

{links_text}
输出: [{{"useful":true/false, "useful_score":0.0-1.0, "result_type":"case/statute/policy/unknown", "matched_goal":"...", "reason":"..."}}]"""

    result = llm._chat_with_diagnostics(
        [{"role": "system", "content": "只输出 JSON 数组。"}, {"role": "user", "content": prompt}],
        0.2, 4096,
    )
    d = result["diagnostics"]
    raw = result.get("content", "")

    parsed, method, diag = parse_deepseek_output(raw)
    default = {"useful": False, "useful_score": 0, "result_type": "unknown", "matched_goal": "", "reason": ""}
    judgments = parse_batch_judgment_results(parsed, links, default) if parsed is not None else []

    success = raw and len(judgments) > 0

    return {
        "success": success, "stage": "link_judge",
        "raw_length": len(raw), "raw_preview": raw[:400],
        "parse_success": parsed is not None, "parse_method": method,
        "judgment_count": len(judgments), "judgments": judgments[:10],
        "deepseek_diagnostics": {
            "status_code": d["status_code"], "choices_count": d["choices_count"],
            "finish_reason": d["finish_reason"], "content_length": d["content_length"],
            "reasoning_length": d["reasoning_length"],
            "prompt_tokens": d["prompt_tokens"], "completion_tokens": d["completion_tokens"],
            "total_tokens": d["total_tokens"], "message_keys": d.get("message_keys", []),
        },
    }


@app.get("/api/sources", response_model=list[SourceItem])
def list_sources() -> list[SourceItem]:
    return get_source_manager().list_all()


@app.post("/api/sources", response_model=SourceItem, status_code=201)
def create_source(item: SourceCreate) -> SourceItem:
    try:
        return get_source_manager().create(item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/sources/{source_id}", response_model=SourceItem)
def update_source(source_id: str, update: SourceUpdate) -> SourceItem:
    result = get_source_manager().update(source_id, update)
    if not result:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return result


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: str) -> dict:
    if not get_source_manager().delete(source_id):
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"success": True}


# ── 附件上传与文字提取 ────────────────────────────

@app.post("/api/attachments/extract", response_model=AttachmentExtractResponse)
async def extract_attachments(
    files: List[UploadFile] = File(...),
    mode: str = Form("append"),
    use_ai_summary: bool = Form(True),
) -> AttachmentExtractResponse:
    """上传附件 → 提取文字 → AI 整理案件详情"""
    warnings: List[str] = []
    file_results: List[AttachmentFileResult] = []
    all_raw_text_parts: List[str] = []

    if mode not in {"append", "replace"}:
        raise HTTPException(status_code=400, detail="mode 仅支持 append 或 replace")

    # 文件数量限制
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="单次最多上传 10 个文件")
    if not files:
        raise HTTPException(status_code=400, detail="请选择至少一个文件")

    upload_dir = ensure_upload_dir()
    temp_paths: List[Path] = []

    for f in files:
        # 读取文件内容
        content = await f.read()
        original_name = f.filename or "unknown"

        # 安全校验
        err = validate_file(original_name, content)
        if err:
            warnings.append(err)
            file_results.append(AttachmentFileResult(
                filename=original_name,
                file_type=Path(original_name).suffix.lower().lstrip("."),
                size=len(content),
                status="failed",
                message=err,
            ))
            continue

        # 保存为安全文件名
        safe_name = safe_filename(original_name)
        file_path = upload_dir / safe_name
        file_path.write_bytes(content)
        temp_paths.append(file_path)

        # 提取文字
        result = extract_text(file_path, original_name)
        file_results.append(AttachmentFileResult(
            filename=original_name,
            file_type=Path(original_name).suffix.lower().lstrip("."),
            size=len(content),
            status=result["status"],
            message=result["message"],
            raw_text_length=result.get("raw_text_length", 0),
            ocr_needed=result.get("ocr_needed", False),
            extract_method=result.get("extract_method", "text_layer" if result["status"] == "success" else "none"),
            ocr_used=result.get("ocr_used", False),
            ocr_engine=result.get("ocr_engine", "none"),
            pages_processed=result.get("pages_processed", 0),
        ))

        if result["status"] == "success" and result.get("raw_text"):
            all_raw_text_parts.append(result["raw_text"])
        elif result.get("message"):
            warnings.append(result["message"])

    # 清理临时文件
    cleanup_temp_files(temp_paths)

    # 汇总原始文字
    raw_text = "\n\n---\n\n".join(all_raw_text_parts)

    if not all_raw_text_parts:
        clean_warnings = list(dict.fromkeys(warnings)) or [
            "未提取到有效文字。请上传可复制文字的 PDF / Word / TXT 文件，或手动粘贴案件内容。"
        ]
        return AttachmentExtractResponse(
            success=False,
            files=file_results,
            raw_text="",
            case_detail_text="",
            warnings=clean_warnings,
        )

    # AI 整理
    case_detail_text = ""
    if use_ai_summary and raw_text.strip():
        case_detail_text = summarize_case_from_attachments(raw_text)

    if not case_detail_text:
        case_detail_text = raw_text[:8000]

    success = any(r.status == "success" for r in file_results)

    return AttachmentExtractResponse(
        success=success,
        files=file_results,
        raw_text=raw_text[:5000] if len(raw_text) > 5000 else raw_text,
        case_detail_text=case_detail_text,
        warnings=warnings,
    )


# ── 分析 ───────────────────────────────────────────
@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = run_analysis(
            request.case_detail,
            request.goals,
            only_verified_links=request.only_verified_links,
            auto_online_search=request.auto_online_search,
            max_keywords_per_goal=request.max_keywords_per_goal,
            max_search_results_per_keyword=request.max_search_results_per_keyword,
            max_links_to_judge=request.max_links_to_judge,
            max_links_to_use=request.max_links_to_use,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析流程失败：{exc}") from exc

    _analysis_store[result["analysis_id"]] = result
    return AnalyzeResponse(**result)


# ── 异步任务分析（推荐） ────────────────────────────

@app.post("/api/analyze/start", response_model=AnalyzeStartResponse)
async def analyze_start(request: AnalyzeStartRequest) -> AnalyzeStartResponse:
    """启动异步分析任务，立即返回 job_id"""
    import asyncio
    import concurrent.futures

    mgr = get_job_manager()
    tracker = mgr.create_job(total_steps=7)

    # 在独立线程中运行同步阻塞的分析工作流，避免阻塞 uvicorn 事件循环
    loop = asyncio.get_event_loop()

    async def _run_in_executor() -> None:
        try:
            await loop.run_in_executor(
                None,
                _run_blocking_workflow,
                tracker,
                request.case_detail,
                request.goals,
                request.auto_online_search,
                request.only_official_sources,
                request.max_keywords_per_goal,
                request.max_search_results_per_keyword,
                request.max_links_to_judge,
                request.max_links_to_use,
            )
        except _JobCancelledError:
            tracker.log("任务已被用户取消", "warning")
        except Exception as exc:
            tracker.log(f"分析失败: {exc}", "error")
            tracker.set_error(str(exc))

    task = asyncio.create_task(_run_in_executor())
    mgr.register_task(tracker.job_id, task)

    return AnalyzeStartResponse(
        success=True,
        job_id=tracker.job_id,
        message="分析任务已启动",
    )


def _run_blocking_workflow(tracker, case_detail, goals, auto_online_search,
                           only_official_sources, max_keywords_per_goal,
                           max_search_results_per_keyword, max_links_to_judge,
                           max_links_to_use):
    """在线程中同步运行工作流（供 run_in_executor 调用）"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_analysis_with_progress(
            tracker=tracker,
            case_detail=case_detail,
            goals_raw=goals,
            auto_online_search=auto_online_search,
            only_official_sources=only_official_sources,
            max_keywords_per_goal=max_keywords_per_goal,
            max_search_results_per_keyword=max_search_results_per_keyword,
            max_links_to_judge=max_links_to_judge,
            max_links_to_use=max_links_to_use,
        ))
    finally:
        loop.close()


@app.get("/api/analyze/progress/{job_id}", response_model=AnalyzeProgressResponse)
def analyze_progress(job_id: str) -> AnalyzeProgressResponse:
    """查询分析任务进度"""
    mgr = get_job_manager()
    data = mgr.get_progress(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return AnalyzeProgressResponse(**data)


@app.get("/api/analyze/result/{job_id}")
def analyze_result(job_id: str) -> dict:
    """获取分析结果（仅任务完成后可用）"""
    mgr = get_job_manager()
    progress = mgr.get_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if progress["status"] == "running" or progress["status"] == "pending":
        return {"success": False, "message": "任务尚未完成", "status": progress["status"]}

    if progress["status"] == "failed":
        return {"success": False, "message": progress.get("error", "分析失败"), "status": "failed"}

    if progress["status"] == "cancelled":
        return {"success": False, "message": "任务已取消", "status": "cancelled"}

    result = mgr.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="结果不存在")

    _analysis_store[result.get("analysis_id", job_id)] = result
    return {"success": True, **result}


@app.post("/api/analyze/cancel/{job_id}", response_model=AnalyzeCancelResponse)
def analyze_cancel(job_id: str) -> AnalyzeCancelResponse:
    """取消分析任务"""
    mgr = get_job_manager()
    if mgr.cancel_job(job_id):
        return AnalyzeCancelResponse(success=True, message="任务已取消")
    raise HTTPException(status_code=404, detail="任务不存在或已完成")


@app.get("/api/online-search/sources")
def list_online_sources() -> list[dict]:
    return online_sources()


@app.put("/api/online-search/sources/{source_id}")
def update_online_source_api(source_id: str, update: OnlineSourceUpdate) -> dict:
    result = update_online_source(source_id, update.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="官方在线来源不存在")
    return result


@app.post("/api/online-search/preview-keywords")
def online_preview_keywords(request: OnlineKeywordRequest) -> dict:
    return preview_keywords(request.case_detail, request.goals, request.max_keywords_per_goal)


@app.post("/api/online-search/search")
def online_search(request: OnlineSearchRequest) -> dict:
    return search_online_index(
        keywords=request.keywords,
        sources=request.sources,
        provider=request.provider,
        max_results_per_keyword=request.max_results_per_keyword,
    )


@app.post("/api/online-search/judge-links")
def online_judge_links(request: OnlineJudgeLinksRequest) -> dict:
    return judge_links(request.case_detail, request.goals, request.links, request.max_links_to_judge)


@app.post("/api/online-search/collect")
def online_collect(request: OnlineCollectRequest) -> dict:
    return collect_online_links(
        case_detail=request.case_detail,
        goals=request.goals,
        sources=request.sources,
        provider=request.provider,
        max_keywords_per_goal=request.max_keywords_per_goal,
        max_results_per_keyword=request.max_results_per_keyword,
        max_links_to_judge=request.max_links_to_judge,
        max_links_to_store=request.max_links_to_store,
    )


@app.get("/api/online-search/logs")
def online_logs() -> list[dict]:
    return get_online_search_client().logs()


@app.get("/api/case-links")
def list_case_links() -> list[dict]:
    return get_case_link_store().list_links()


@app.put("/api/case-links/{link_id}")
def update_case_link(link_id: str, update: CaseLinkUpdate) -> dict:
    result = get_case_link_store().update_link(link_id, update.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="链接不存在")
    return result


@app.delete("/api/case-links/{link_id}")
def delete_case_link(link_id: str) -> dict:
    if not get_case_link_store().delete_link(link_id):
        raise HTTPException(status_code=404, detail="链接不存在")
    return {"success": True}


@app.post("/api/cases/search", response_model=CaseSearchResponse)
def search_cases(request: CaseSearchRequest) -> CaseSearchResponse:
    goals = split_goals(request.goals)
    result = get_case_search_engine().search_cases(request.case_detail, goals, request.keywords, request.top_k)
    return CaseSearchResponse(cases=[CaseReference(**case) for case in result["cases"]], warnings=result["warnings"])


@app.post("/api/cases/rank", response_model=CaseRankResponse)
def rank_cases(request: CaseRankRequest) -> CaseRankResponse:
    result = get_case_ranker().rank_cases(request.case_detail, request.goals, request.candidate_cases)
    return CaseRankResponse(
        ranked_cases=[CaseReference(**case) for case in result["ranked_cases"]],
        warnings=result["warnings"],
    )


@app.post("/api/review/legal-model", response_model=ReviewResult)
def review_legal_model(request: LegalReviewRequest) -> ReviewResult:
    review = review_legal_analysis(request.case_detail, request.goals, request.analysis_markdown, request.cases)
    return ReviewResult(**review)


@app.post("/api/export/docx", response_model=ExportDocxResponse)
def export_docx(request: ExportDocxRequest) -> ExportDocxResponse:
    markdown = request.markdown
    cases = request.cases
    if request.analysis_id and request.analysis_id in _analysis_store:
        cached = _analysis_store[request.analysis_id]
        markdown = cached.get("markdown", markdown)
        cases = cached.get("cases", cases)

    file_id, filename = get_report_generator().generate(markdown, cases)
    return ExportDocxResponse(success=True, file_id=file_id, filename=filename, message="Word 文件已生成")


@app.get("/api/download/{file_id}")
def download_file(file_id: str) -> FileResponse:
    file_path = get_report_generator().resolve_file(file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在，请先生成 Word 文件")
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
