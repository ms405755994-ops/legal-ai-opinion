from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    id: str
    name: str
    url: str
    type: str = "other"
    enabled: bool = True
    note: str = ""


class SourceCreate(BaseModel):
    id: str = Field(..., min_length=2)
    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    type: str = "other"
    enabled: bool = True
    note: str = ""


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    note: Optional[str] = None


class OnlineSourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    allow_online_index_search: Optional[bool] = None
    allow_direct_fetch: Optional[bool] = None
    stop_if_login_or_captcha: Optional[bool] = None
    search_query_prefix: Optional[str] = None
    note: Optional[str] = None


class ModelStatusEntry(BaseModel):
    enabled: bool
    mode: str
    role: str


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    backend: str = "fastapi"


class AnalyzeRequest(BaseModel):
    case_detail: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    only_verified_links: bool = False
    auto_online_search: bool = True
    only_official_sources: bool = True
    max_keywords_per_goal: int = Field(default=8, ge=1, le=20)
    max_search_results_per_keyword: int = Field(default=10, ge=1, le=50)
    max_links_to_judge: int = Field(default=30, ge=1, le=100)
    max_links_to_use: int = Field(default=8, ge=1, le=50)


class CaseReference(BaseModel):
    id: Optional[str] = None
    title: str = ""
    case_no: str = ""
    court: str = ""
    judgment_date: str = ""
    issue: str = ""
    holding: str = ""
    facts: str = ""
    url: str = ""
    source_name: str = ""
    source_id: str = ""
    domain: str = ""
    is_mock: bool = False
    online_indexed: bool = False
    verified: bool = False
    can_be_used_as_formal_citation: bool = False
    snippet: str = ""
    need_human_verify: bool = True
    matched_goal: str = ""
    matched_issue: str = ""
    similarity_score: float = 0.0
    support_strength: str = "不足"
    reason: str = ""


class ReviewResult(BaseModel):
    legal_relation_check: str = ""
    case_usage_check: str = ""
    missing_issues: List[str] = Field(default_factory=list)
    risk_warnings: List[str] = Field(default_factory=list)
    overclaim_risks: List[str] = Field(default_factory=list)
    final_review_level: str = "需要人工复核"
    reviewer: str = "mock"


class AnalyzeResponse(BaseModel):
    success: bool
    analysis_id: str
    html: str
    markdown: str
    cases: List[CaseReference] = Field(default_factory=list)
    review: ReviewResult = Field(default_factory=ReviewResult)
    warnings: List[str] = Field(default_factory=list)
    docx_file_id: Optional[str] = None
    case_mode: str = "none"
    can_be_used_for_real_case: bool = False
    real_case_count: int = 0
    mock_case_count: int = 0
    verified_case_count: int = 0
    unverified_case_count: int = 0
    report_mode: str = "test_mock"
    case_search_mode: str = "online_auto"
    auto_online_search: bool = True
    keywords: List[str] = Field(default_factory=list)
    search_summary: Dict[str, Any] = Field(default_factory=dict)
    used_links: List[Dict[str, Any]] = Field(default_factory=list)


class CaseSearchRequest(BaseModel):
    case_detail: str = ""
    goals: str = ""
    keywords: List[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)


class CaseSearchResponse(BaseModel):
    cases: List[CaseReference] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CaseRankRequest(BaseModel):
    case_detail: str
    goals: List[str] = Field(default_factory=list)
    candidate_cases: List[Dict[str, Any]] = Field(default_factory=list)


class CaseRankResponse(BaseModel):
    ranked_cases: List[CaseReference] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class LegalReviewRequest(BaseModel):
    case_detail: str
    goals: List[str] = Field(default_factory=list)
    analysis_markdown: str = ""
    cases: List[Dict[str, Any]] = Field(default_factory=list)


class ExportDocxRequest(BaseModel):
    analysis_id: Optional[str] = None
    markdown: str
    cases: List[Dict[str, Any]] = Field(default_factory=list)


class ExportDocxResponse(BaseModel):
    success: bool
    file_id: str
    filename: str
    message: str = ""


class OnlineKeywordRequest(BaseModel):
    case_detail: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    max_keywords_per_goal: Optional[int] = Field(default=None, ge=1, le=20)


class OnlineSearchRequest(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    max_results_per_keyword: Optional[int] = Field(default=None, ge=1, le=50)


class OnlineJudgeLinksRequest(BaseModel):
    case_detail: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    max_links_to_judge: Optional[int] = Field(default=None, ge=1, le=100)


class OnlineCollectRequest(BaseModel):
    case_detail: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    sources: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    max_keywords_per_goal: Optional[int] = Field(default=None, ge=1, le=20)
    max_results_per_keyword: Optional[int] = Field(default=None, ge=1, le=50)
    max_links_to_judge: Optional[int] = Field(default=None, ge=1, le=100)
    max_links_to_store: Optional[int] = Field(default=None, ge=1, le=50)


class CaseLinkUpdate(BaseModel):
    verified: Optional[bool] = None
    need_human_verify: Optional[bool] = None
    can_be_used_as_formal_citation: Optional[bool] = None
    support_strength: Optional[str] = None
    matched_goal: Optional[str] = None
    matched_issue: Optional[str] = None


# ── 异步任务分析 ───────────────────────────────────

class AnalyzeStartRequest(BaseModel):
    case_detail: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    auto_online_search: bool = True
    only_official_sources: bool = True
    max_keywords_per_goal: int = Field(default=8, ge=1, le=20)
    max_search_results_per_keyword: int = Field(default=10, ge=1, le=50)
    max_links_to_judge: int = Field(default=30, ge=1, le=100)
    max_links_to_use: int = Field(default=8, ge=1, le=50)


class AnalyzeStartResponse(BaseModel):
    success: bool
    job_id: str
    message: str = "分析任务已启动"


class AnalyzeProgressResponse(BaseModel):
    job_id: str
    status: str
    current_step: str = "initializing"
    current_step_label: str = "正在初始化"
    step_index: int = 0
    total_steps: int = 6
    percent: int = 0
    elapsed_seconds: int = 0
    logs: list = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    error: Optional[str] = None


class AnalyzeCancelResponse(BaseModel):
    success: bool
    message: str


# ── 附件上传 ────────────────────────────────────────

class AttachmentFileResult(BaseModel):
    filename: str
    file_type: str
    size: int
    status: str  # waiting / extracting / success / failed
    message: str = ""
    raw_text_length: int = 0
    ocr_needed: bool = False
    extract_method: str = "none"  # text_layer / ocr / none
    ocr_used: bool = False
    ocr_engine: str = "none"
    pages_processed: int = 0


class AttachmentExtractResponse(BaseModel):
    success: bool
    files: List[AttachmentFileResult] = Field(default_factory=list)
    raw_text: str = ""
    case_detail_text: str = ""
    warnings: List[str] = Field(default_factory=list)
