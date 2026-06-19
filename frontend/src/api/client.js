const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

// ── 令牌存储（仅保存在用户浏览器 localStorage，不会打包进静态 JS） ──
const TOKEN_KEY = 'LEGAL_AI_ACCESS_TOKEN'

function getAccessToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setAccessToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch { /* 无痕浏览等不可用 */ }
}

export function clearAccessToken() {
  setAccessToken('')
}

export function hasAccessToken() {
  return Boolean(getAccessToken())
}

export function getMaskedToken() {
  const token = getAccessToken()
  if (!token) return ''
  if (token.length <= 8) return '****'
  return token.slice(0, 4) + '****' + token.slice(-4)
}

function authHeaders(extraHeaders = {}) {
  const token = getAccessToken()
  if (token) {
    return { ...extraHeaders, Authorization: `Bearer ${token}` }
  }
  return extraHeaders
}

// ── 请求封装 ──
async function request(path, options = {}) {
  const headers = authHeaders({
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  })

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = payload.detail || `HTTP ${response.status}`
    const err = new Error(detail)
    err.status = response.status
    throw err
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response
}

const api = {
  baseUrl: API_BASE,
  health: () => request('/api/health'),
  modelStatus: () => request('/api/model-status'),
  getSources: () => request('/api/sources'),
  createSource: (payload) =>
    request('/api/sources', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateSource: (id, payload) =>
    request(`/api/sources/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  deleteSource: (id) =>
    request(`/api/sources/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    }),
  analyze: (caseDetail, goals) =>
    request('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ case_detail: caseDetail, goals })
    }),
  analyzeWithOptions: (caseDetail, goals, options = {}) =>
    request('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ case_detail: caseDetail, goals, ...options })
    }),
  analyzeStart: (caseDetail, goals, options = {}) =>
    request('/api/analyze/start', {
      method: 'POST',
      body: JSON.stringify({ case_detail: caseDetail, goals, ...options })
    }),
  analyzeProgress: (jobId) =>
    request(`/api/analyze/progress/${encodeURIComponent(jobId)}`),
  analyzeResult: (jobId) =>
    request(`/api/analyze/result/${encodeURIComponent(jobId)}`),
  analyzeCancel: (jobId) =>
    request(`/api/analyze/cancel/${encodeURIComponent(jobId)}`, {
      method: 'POST'
    }),
  searchCases: (payload) =>
    request('/api/cases/search', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  rankCases: (payload) =>
    request('/api/cases/rank', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  reviewLegalModel: (payload) =>
    request('/api/review/legal-model', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  exportDocx: (markdown, cases, analysisId) =>
    request('/api/export/docx', {
      method: 'POST',
      body: JSON.stringify({ markdown, cases, analysis_id: analysisId })
    }),
  downloadUrl: (fileId) => `${API_BASE}/api/download/${encodeURIComponent(fileId)}`,
  /** 带 Authorization 令牌的文件下载（返回 Blob） */
  downloadFile: async (fileId) => {
    const headers = authHeaders()
    const response = await fetch(`${API_BASE}/api/download/${encodeURIComponent(fileId)}`, { headers })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }))
      const detail = payload.detail || `HTTP ${response.status}`
      const err = new Error(detail)
      err.status = response.status
      throw err
    }
    return response.blob()
  },
  getOnlineSources: () => request('/api/online-search/sources'),
  providerStatus: () => request('/api/online-search/provider-status'),
  updateOnlineSource: (id, payload) =>
    request(`/api/online-search/sources/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  previewOnlineKeywords: (payload) =>
    request('/api/online-search/preview-keywords', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  searchOnline: (payload) =>
    request('/api/online-search/search', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  judgeOnlineLinks: (payload) =>
    request('/api/online-search/judge-links', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  collectOnlineLinks: (payload) =>
    request('/api/online-search/collect', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  getOnlineLogs: () => request('/api/online-search/logs'),
  configRuntime: () => request('/api/config/runtime'),

  // DeepSeek 诊断
  deepseekHealth: () => request('/api/deepseek/health'),
  testKeywordGeneration: (caseDetail, goals) =>
    request('/api/deepseek/test-keyword-generation', {
      method: 'POST',
      body: JSON.stringify({ case_detail: caseDetail, goals })
    }),
  testLinkJudge: (caseDetail, goals, links) =>
    request('/api/deepseek/test-link-judge', {
      method: 'POST',
      body: JSON.stringify({ case_detail: caseDetail, goals, links })
    }),

  getCaseLinks: () => request('/api/case-links'),
  updateCaseLink: (id, payload) =>
    request(`/api/case-links/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  deleteCaseLink: (id) =>
    request(`/api/case-links/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    }),

  // 附件上传与文字提取（multipart/form-data，不设 Content-Type 让浏览器自动设置）
  extractAttachments: async (formData) => {
    let resp
    try {
      resp = await fetch(`${API_BASE}/api/attachments/extract`, {
        method: 'POST',
        body: formData
      })
    } catch {
      throw new Error('附件上传失败，请确认后端服务已启动。')
    }

    if (!resp.ok) {
      if (resp.status === 404) {
        throw new Error('附件解析接口不存在，请检查后端 /api/attachments/extract 是否已启动。')
      }
      const payload = await resp.json().catch(() => ({ detail: resp.statusText }))
      const detail = Array.isArray(payload.detail)
        ? payload.detail.map((item) => item.msg).join('；')
        : (payload.detail || `HTTP ${resp.status}`)
      throw new Error(detail)
    }
    return resp.json()
  }
}

export default api
