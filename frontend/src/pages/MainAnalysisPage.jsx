import { Play, Search } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import api, { hasAccessToken } from '../api/client.js'
import AnalyzeProgressPanel from '../components/AnalyzeProgressPanel.jsx'
import AttachmentUploader from '../components/AttachmentUploader.jsx'
import CaseInput from '../components/CaseInput.jsx'
import CasePresetsBar from '../components/CasePresetsBar.jsx'
import GoalInput from '../components/GoalInput.jsx'
import ResultViewer from '../components/ResultViewer.jsx'

const disclaimer =
  '本系统仅用于类案检索、法律问题初步分析、案件处理思路整理和文书准备参考，不构成正式法律意见，不替代执业律师服务。系统输出可能存在遗漏、错误或不适用于具体案件的情况。正式提交法院、仲裁机构、行政机关或用于重大决策前，请务必由执业律师进行人工复核。'

export default function MainAnalysisPage() {
  const [caseDetail, setCaseDetail] = useState('')
  const [goals, setGoals] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [resultMsg, setResultMsg] = useState('')
  const [msgType, setMsgType] = useState('')
  const [modelStatus, setModelStatus] = useState({})

  // 异步任务状态
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [cancelled, setCancelled] = useState(false)
  const [staleWarning, setStaleWarning] = useState(false)
  const pollRef = useRef(null)
  const lastUpdateRef = useRef(0)
  const activeJobRef = useRef(null)

  useEffect(() => {
    api.modelStatus().then(setModelStatus).catch(() => setModelStatus({}))
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [])

  const onlineSearchReady = Boolean(modelStatus.online_search?.enabled)

  function handleExtractedText(text, mode) {
    if (mode === 'replace' || !caseDetail.trim()) {
      setCaseDetail(text)
    } else {
      setCaseDetail(prev => prev + '\n\n' + text)
    }
  }

  function handleFillPreset(text, presetGoals, presetName) {
    setCaseDetail(text)
    if (presetGoals) {
      setGoals(presetGoals)
    }
    setResultMsg(`已填入${presetName}和希望结果，可继续修改后开始一键深度分析。`)
    setMsgType('success')
  }

  // ── 轮询进度 ──
  const startPolling = useCallback((jid) => {
    let staleTimer = null
    activeJobRef.current = jid
    lastUpdateRef.current = Date.now()

    const poll = async () => {
      if (activeJobRef.current !== jid) return
      try {
        const p = await api.analyzeProgress(jid)
        if (activeJobRef.current !== jid) return
        setProgress(p)
        lastUpdateRef.current = Date.now()
        setStaleWarning(false)
        if (staleTimer) { clearTimeout(staleTimer); staleTimer = null }

        if (p.status === 'completed') {
          const res = await api.analyzeResult(jid)
          if (activeJobRef.current !== jid) return
          if (res.success) {
            setResult(res)
          } else {
            setError(res.message || '分析完成但获取结果失败')
          }
          setLoading(false)
          return
        }

        if (p.status === 'failed') {
          setError(p.error || '分析失败')
          setLoading(false)
          return
        }

        if (p.status === 'cancelled') {
          setCancelled(true)
          setLoading(false)
          return
        }

        if (p.elapsed_seconds > 600) {
          setError('任务超时，请检查 DeepSeek / Tavily API 或后端日志。')
          setLoading(false)
          return
        }

        staleTimer = setTimeout(() => setStaleWarning(true), 30000)
        pollRef.current = setTimeout(poll, 1000)
      } catch (err) {
        setError(err.message || '获取进度失败')
        setLoading(false)
      }
    }

    poll()
  }, [])

  // ── 开始分析 ──
  async function analyze() {
    if (pollRef.current) {
      clearTimeout(pollRef.current)
      pollRef.current = null
    }
    activeJobRef.current = null
    setError('')
    setResult(null)
    setProgress(null)
    setCancelled(false)
    setStaleWarning(false)

    if (!caseDetail.trim()) return setError('请输入当前案件详情')
    if (!goals.trim()) return setError('请输入希望结果')

    setLoading(true)
    try {
      const startResp = await api.analyzeStart(caseDetail, goals, {
        auto_online_search: true,
        only_official_sources: true,
        max_keywords_per_goal: 5,
        max_search_results_per_keyword: 8,
        max_links_to_judge: 15,
        max_links_to_use: 5
      })

      if (!startResp.success) {
        setError(startResp.message || '启动分析失败')
        setLoading(false)
        return
      }

      setJobId(startResp.job_id)
      activeJobRef.current = startResp.job_id
      startPolling(startResp.job_id)
    } catch (err) {
      if (err.message.includes('fetch')) {
        setError(`无法连接本机后端：${api.baseUrl}`)
      } else if (err.status === 401 || err.message.includes('访问令牌')) {
        setError('401 访问令牌未设置或无效，请在右上角点击「访问令牌」按钮设置。')
      } else {
        setError(err.message)
      }
      setLoading(false)
    }
  }

  // ── 取消分析 ──
  async function cancelAnalysis() {
    if (!jobId) return
    try {
      await api.analyzeCancel(jobId)
      if (activeJobRef.current === jobId) {
        activeJobRef.current = null
      }
      setCancelled(true)
      setLoading(false)
    } catch (err) {
      setError(err.message || '取消失败')
    }
  }

  return (
    <>
      <section className="disclaimer-band">{disclaimer}</section>
      <section className="analysis-input-layout">
        <div className="case-input-group">
          <CasePresetsBar
            currentValue={caseDetail}
            goalsValue={goals}
            onFillPreset={handleFillPreset}
            disabled={loading}
          />
          {resultMsg && (
            <div className={`upload-result-msg ${msgType}`}>
              {resultMsg}
            </div>
          )}
          <AttachmentUploader
            value={caseDetail}
            onExtractedText={handleExtractedText}
            disabled={loading}
          />
          <CaseInput value={caseDetail} onChange={setCaseDetail} disabled={loading} />
        </div>
        <aside className="analysis-side">
          <GoalInput value={goals} onChange={setGoals} disabled={loading} />
          <section className="auto-settings">
            <div className="section-kicker"><Search size={16} />自动检索设置摘要</div>
            <dl>
              <div><dt>检索模式</dt><dd>自动在线索引</dd></div>
              <div><dt>来源范围</dt><dd>仅官方法律网站</dd></div>
              <div><dt>关键词</dt><dd>每个目标最多 8 个</dd></div>
              <div><dt>搜索结果</dt><dd>每个关键词最多 10 条</dd></div>
              <div><dt>AI 判断</dt><dd>最多 30 个链接</dd></div>
              <div><dt>报告引用</dt><dd>最多 8 个链接</dd></div>
            </dl>
          </section>
        </aside>
      </section>
      {error && (
        <div className={`notice ${error.startsWith('401') ? 'notice-warn' : 'notice-error'}`}>
          {error.startsWith('401') ? (
            <>
              <strong>{error}</strong>
              {!hasAccessToken() && (
                <p style={{ margin: '8px 0 0' }}>
                  请点击页面右上角的 <code>未设置令牌</code> 按钮，输入与后端一致的访问令牌。
                </p>
              )}
            </>
          ) : (
            error
          )}
        </div>
      )}
      {!onlineSearchReady && (
        <div className="notice notice-warn">
          当前未配置在线搜索 API Key，系统无法自动检索真实案例链接。请在 backend/.env 中配置 Tavily API Key（推荐），或 Google CSE / Bing（备选）。
        </div>
      )}
      <div className="analysis-bar">
        <button className="primary-button large" type="button" disabled={loading} onClick={analyze}>
          <Play size={18} />
          {loading ? '一键深度分析中' : '开始一键深度分析'}
        </button>
        <span>系统会自动从已配置的官方在线来源中检索案例链接，检索到的有用链接会自动保存到“自动检索结果库”。</span>
      </div>
      {/* 实时进度 */}
      {loading && progress && (
        <>
          <AnalyzeProgressPanel
            progress={progress}
            onCancel={cancelAnalysis}
            cancelled={cancelled}
          />
          {staleWarning && (
            <div className="notice notice-warn">
              {progress?.current_step === 'generating_keywords'
                ? '正在等待 DeepSeek 生成检索关键词，Tavily 尚未开始搜索。'
                : '长时间未收到新进度，后端可能仍在等待当前步骤返回，请稍候。'}
            </div>
          )}
        </>
      )}

      {/* 结果展示 */}
      <div id="result-section">{result && <ResultViewer result={result} />}</div>
    </>
  )
}
