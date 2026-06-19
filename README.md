# legal-ai-opinion

AI 类案检索助手。前端可部署到 GitHub Pages，后端必须在本机运行，前端统一通过 `http://127.0.0.1:8000` 调用后端。

## 1. 项目介绍

本项目用于将案件事实、用户目标、类案检索、案例排序、引用校验、法律复核和 Word 报告生成串成一条可运行链路。V1 使用 DeepSeek API 或本地 mock 输出完成案件拆解和关键词生成，类案数据、Lawformer、DISC-LawLLM、InternLM-Law 默认均可 mock。

## 2. 系统定位

系统定位是“类案检索助手”，不是正式律师意见生成器。

法律免责声明：本系统仅用于类案检索、法律问题初步分析、案件处理思路整理和文书准备参考，不构成正式法律意见，不替代执业律师服务。系统输出可能存在遗漏、错误或不适用于具体案件的情况。正式提交法院、仲裁机构、行政机关或用于重大决策前，请务必由执业律师进行人工复核。

## 3. 架构图

```text
┌─────────────────────────────────────────────────────┐
│  外部网络                                            │
│  GitHub Pages / Vite React                          │
│  https://用户名.github.io/legal-ai-opinion/          │
└────────┬────────────────────────────────────────────┘
         │ HTTPS (Authorization: Bearer TOKEN)
         v
┌────────┴────────────────────────────────────────────┐
│  Cloudflare Tunnel（公网 HTTPS）                      │
│  https://xxxx.trycloudflare.com                      │
└────────┬────────────────────────────────────────────┘
         │
         v
┌────────┴────────────────────────────────────────────┐
│  本机 127.0.0.1:8000                                 │
│  FastAPI Backend                                     │
│       │                                              │
│       +── DeepSeek API: 案件拆解、关键词生成            │
│       +── Tavily API: 在线检索                        │
│       +── case_search: 案例检索                       │
│       +── python-docx: Word 报告                      │
└─────────────────────────────────────────────────────┘
```

> DeepSeek API Key / Tavily API Key 仅保存在本机 `backend/.env`，不上传 GitHub。

## 4. 模型分工

DeepSeek：主分析模型，负责案件拆解、诉求拆解、检索关键词生成。

Lawformer：类案相似度排序模型，V1 默认 mock。

DISC-LawLLM / InternLM-Law：法律复核模型，V1 默认 mock。

ChatLaw：仅参考 RAG、多 Agent、知识库和幻觉控制架构。

## 5. 为什么前端可以放 GitHub，后端必须放本机

前端只保存页面代码和本机后端地址，不保存 DeepSeek Key，不直接调用 DeepSeek 或任何法律模型。DeepSeek API Key 只放在 `backend/.env`，所有模型调用、数据源访问、Word 生成都由本机 FastAPI 后端完成。

## 6. 本机后端启动方法

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## 7. 前端本地启动方法

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

## 8. 部署模式

### 本地开发模式

前后端均在本机运行：

```powershell
# 终端 1：启动后端
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 终端 2：启动前端
cd frontend
npm run dev
```

前端访问 `http://127.0.0.1:5173`，后端监听 `http://127.0.0.1:8000`。

### 外部访问模式（GitHub Pages + Cloudflare Tunnel）

```
外部用户 → GitHub Pages（前端）→ Cloudflare Tunnel（公网 HTTPS）→ 本机 FastAPI（后端）
```

**后端不变**，仍在本机 `127.0.0.1:8000`。**前端部署到 GitHub Pages**，通过 Cloudflare Tunnel 将本机后端暴露为公网 HTTPS 地址。

#### 步骤

1. **启动本机后端**（同上）
2. **启动 Cloudflare Tunnel**：
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
   得到公网地址如 `https://xxxx.trycloudflare.com`
3. **配置 GitHub Actions Variable**：在仓库 Settings → Secrets and variables → Actions → Variables 设置 `VITE_API_BASE_URL` = `https://xxxx.trycloudflare.com`
4. **推送代码**，GitHub Actions 自动构建并部署到 GitHub Pages
5. **配置后端令牌**：在 `backend/.env` 中设置：
   ```env
   APP_ENV=production
   APP_ACCESS_TOKEN=你的强随机令牌
   ```
6. **用户在前端输入令牌**：打开 GitHub Pages 页面，点击右上角「未设置令牌」，输入与后端一致的令牌。

详细说明见 [docs/deploy_cloudflare_tunnel.md](docs/deploy_cloudflare_tunnel.md)。

#### 安全验证清单

部署完成后，逐项验证：

| # | 验证项 | 预期结果 |
|---|--------|----------|
| 1 | GitHub Pages 打开前端页面 | 页面正常加载，无 404 |
| 2 | 页面显示「后端 OK」 | `/api/health` 可访问，模型状态正常 |
| 3 | 未设置令牌时发起分析 | 返回 401 并提示"请设置访问令牌" |
| 4 | 前端 JS 搜索 token 关键字 | 搜不到真实 `APP_ACCESS_TOKEN` |
| 5 | GitHub 仓库搜索 DeepSeek Key | 搜不到真实 Key |
| 6 | GitHub 仓库搜索 Tavily Key | 搜不到真实 Key |
| 7 | 设置正确令牌后分析 | 正常分析，返回结果 |
| 8 | Word 下载 | `.docx` 文件正常生成和下载 |

> **令牌安全**：前端不内置令牌。用户在浏览器中输入令牌，保存在 localStorage。后端真实令牌只在本机 `backend/.env`，不会上传 GitHub，也不会打包进前端 JS。

#### GitHub Pages 手动部署

```powershell
cd frontend
npm run build
```

只部署 `frontend/dist`。使用 GitHub Pages 页面前，必须先在本机启动 `backend` 和 `cloudflared tunnel`。

## 9. DeepSeek Key 配置方法

在 `backend/.env` 中配置：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-reasoner
DEEPSEEK_REASONING_EFFORT=max
```

前端 `.env.local`（本地覆盖，不提交 Git）：

```env
# 本地开发（默认）
VITE_API_BASE_URL=http://127.0.0.1:8000
# Cloudflare Tunnel 部署时改为公网地址
# VITE_API_BASE_URL=https://xxxx.trycloudflare.com
# ⚠️ 令牌不再通过环境变量设置！请打开页面后在右上角「访问令牌」输入。
```

## 10. 附件上传与案件详情自动整理

主分析页和高级调试页的「案件详情」区域均支持上传附件。

**支持的文件类型**：PDF、DOCX、TXT、MD、CSV、JSON

**使用流程**：
1. 在「上传案件附件」区域点击上传或拖拽文件
2. 系统自动提取附件文字
3. DeepSeek 将附件文字整理成结构化案件详情
4. 整理后的内容自动填入案件详情输入框
5. 用户可选择「替换当前内容」或「追加到当前内容」
6. 检查并手动修改后，点击「开始一键深度分析」

**限制**：
- 单文件最大 20 MB
- 单次最多 10 个文件
- 上传文件在提取完成后自动删除，不会保留在服务器上
- 图片和扫描件 PDF 支持 OCR 识别（需启用 PaddleOCR）

## OCR 识别说明

对于扫描版 PDF、图片 PDF、JPG、PNG 等文件，系统支持通过 PaddleOCR 进行文字识别。

**启用方法**：在 `backend/.env` 中设置：

```env
ENABLE_OCR=true
OCR_PROVIDER=paddleocr
OCR_LANGUAGE=ch
OCR_MAX_PAGES=20
OCR_DPI=200
```

**Windows CPU 安装命令**：

```bash
# 先安装 PaddlePaddle CPU 版
pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# 再安装 OCR 相关依赖
pip install paddleocr pymupdf pillow
```

**注意事项**：
- OCR 速度较慢，扫描 PDF 每页可能需要数秒，大文件可能需 1-3 分钟
- OCR 结果可能有错别字，正式分析前需人工检查
- 单个 PDF 最多 OCR 前 20 页（可通过 OCR_MAX_PAGES 调整）
- 如果需要 PaddleOCR GPU 版，请参考 [PaddleOCR 官方文档](https://github.com/PaddlePaddle/PaddleOCR)
- OCR 中间图片默认不保存，设置 `OCR_SAVE_DEBUG_IMAGES=true` 可保留调试图片

**如果 PaddlePaddle 安装遇到问题**：
1. 确认 Python 版本为 3.8-3.12
2. 确认使用 Windows 64 位系统
3. 或参考 PaddlePaddle 官方安装指南：https://www.paddlepaddle.org.cn/install/quick

**安全**：
- 上传文件保存为 UUID 安全文件名
- 后端仅监听 `127.0.0.1`，外部无法访问
- `backend/uploads/` 目录已加入 `.gitignore`，不会提交到 GitHub

## 11. 数据源设置方法

“数据源设置”页面只配置官方在线来源白名单、搜索 Provider 状态、是否启用、是否允许直接访问公开页面、遇到登录/验证码是否停止。自动检索到的有用链接不在这里手动配置，而是由主分析流程自动保存到 `backend/data/case_links.json`。

V1 默认使用 `backend/data/mock_cases.json`，所有模拟案例均带 `is_mock=true` 和 `mock://` 链接。

## 12. 在线索引模式

当前推荐使用 `CASE_SEARCH_MODE=online_index`。主分析页已内置自动在线索引检索：用户只需要输入案件详情和希望结果，点击“开始一键深度分析”，系统会自动生成关键词，通过 Bing、Tavily 或 Google CSE 在线搜索官方法律网站，自动筛选有用链接并生成报告和 Word。

“在线检索调试”页面仅用于测试搜索 API、关键词、数据源和链接筛选效果，不是正式分析前置步骤。

新增数据文件：

- `backend/data/online_sources.json`
- `backend/data/case_links.json`
- `backend/data/online_search_logs.json`

`/api/analyze` 是唯一主入口，会自动执行在线索引检索，不搜索 `local_cases`，不使用 GitHub 数据集，不把 mock 案例作为正式支持。

自动分析保存到 `case_links.json` 的链接会标记：

```json
{
  "auto_collected": true,
  "used_in_analysis": true,
  "verified": false,
  "can_be_used_as_formal_citation": false
}
```

报告中会显示为“AI 自动检索待核验参考链接”。人工在“自动检索结果库”标记 `verified=true` 后，后续报告才会显示为“已核验在线案例链接”。

## Bing Custom Search 配置

```env
ONLINE_SEARCH_PROVIDER=bing
BING_SEARCH_API_KEY=
BING_CUSTOM_CONFIG_ID=
BING_SEARCH_ENDPOINT=https://api.bing.microsoft.com/v7.0/custom/search
```

## Tavily 配置

```env
ONLINE_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=
```

## Google CSE 配置

```env
ONLINE_SEARCH_PROVIDER=google_cse
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_CX=
```

## 官方数据源配置

在线搜索范围由 `backend/data/online_sources.json` 限定，默认包括最高人民法院官网、最高人民法院公报、人民法院案例库、最高人民检察院案例等官方域名。系统只允许保存这些官方域名中的链接；商业数据库、论坛、博客、公众号转载默认跳过。

## 合规边界

系统只调用在线搜索索引 API，不绕过登录、验证码、授权、付费墙或反爬限制。`allow_direct_fetch=false` 的来源只保存搜索 API 返回的标题、摘要和 URL，不直接抓取网页。页面返回 403、429、登录、验证码或访问受限时，会记录 `skipped_reason` 并跳过。

## verified=true 才能正式引用

在线检索保存的链接默认：

```json
{
  "verified": false,
  "online_indexed": true,
  "can_be_used_as_formal_citation": false
}
```

`verified=false` 只能显示为“在线检索待核验参考链接”。人工打开原始链接核验后，在“自动检索结果库”中标记 `verified=true`，才可作为“已核验在线案例链接”进入正式引用范围。

## 11. Lawformer 接入预留说明

配置：

```env
USE_LAWFORMER=false
LAWFORMER_MODE=mock
LAWFORMER_LOCAL_URL=http://127.0.0.1:8011
```

真实服务可实现 `POST /rank`，返回 `ranked_cases`。

## 12. DISC-LawLLM 接入预留说明

配置：

```env
USE_DISC_LAWLLM=false
DISC_LAWLLM_MODE=mock
DISC_LAWLLM_LOCAL_URL=http://127.0.0.1:8012
```

真实服务可实现 `POST /review`。

## 13. InternLM-Law 接入预留说明

配置：

```env
USE_INTERNLM_LAW=false
INTERNLM_LAW_MODE=mock
INTERNLM_LAW_LOCAL_URL=http://127.0.0.1:8013
```

DISC-LawLLM 优先；DISC 未启用但 InternLM-Law 启用时使用 InternLM-Law；两者都未启用时使用 mock review。

## 14. ChatLaw 架构参考说明

见 `backend/legal_models/chatlaw_reference/architecture_notes.md`。V1 不强制部署 ChatLaw，仅参考其检索增强、多 Agent、知识库和幻觉控制思路。

## 15. Word 下载说明

`POST /api/analyze` 会自动生成 Word，并返回 `docx_file_id`。前端报告区右上角“下载 Word”调用：

```text
GET /api/download/{file_id}
```

文件保存在 `backend/outputs/`，命名格式为 `legal_analysis_YYYYMMDD_HHMMSS.docx`。

## 16. 防幻觉规则

系统提示词和报告生成器都要求：

- 不得编造案例、案号、法院、裁判观点、链接。
- 只能使用检索模块返回的 `cases`。
- mock 案例必须明确标记。
- 没有可核验真实案例链接时，必须标记案例支持不足。
- 不得承诺胜诉，不得替代律师。

## 17. 法律免责声明

本系统仅用于类案检索、法律问题初步分析、案件处理思路整理和文书准备参考，不构成正式法律意见，不替代执业律师服务。系统输出可能存在遗漏、错误或不适用于具体案件的情况。正式提交法院、仲裁机构、行政机关或用于重大决策前，请务必由执业律师进行人工复核。

## 18. 后续开发路线

见 `docs/future-integration-plan.md`。
