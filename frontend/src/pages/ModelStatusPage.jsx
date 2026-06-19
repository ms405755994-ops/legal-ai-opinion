import { Activity, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Loader, Search, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import api from '../api/client.js'
import ModelStatusPanel from '../components/ModelStatusPanel.jsx'

export default function ModelStatusPage() {
  const [status, setStatus] = useState({})
  const [error, setError] = useState('')

  // DeepSeek 诊断状态
  const [diagHealth, setDiagHealth] = useState(null)
  const [diagConfig, setDiagConfig] = useState(null)
  const [diagKeyword, setDiagKeyword] = useState(null)
  const [diagTestDetail, setDiagTestDetail] = useState('')
  const [diagTestGoals, setDiagTestGoals] = useState('')
  const [diagRunning, setDiagRunning] = useState('')
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    api.modelStatus().then(setStatus).catch((err) => setError(err.message))
  }, [])

  async function runHealthCheck() {
    setDiagRunning('health')
    setDiagHealth(null)
    setDiagConfig(null)
    setError('')
    try {
      const [health, config] = await Promise.all([
        api.deepseekHealth(),
        api.configRuntime(),
      ])
      setDiagHealth(health)
      setDiagConfig(config)
    } catch (e) {
      setDiagHealth({ success: false, last_error: e.message })
    }
    setDiagRunning('')
  }

  async function runKeywordTest() {
    if (!diagTestDetail.trim()) return setError('请输入测试案件详情')
    setDiagRunning('keyword')
    setDiagKeyword(null)
    try {
      setDiagKeyword(await api.testKeywordGeneration(diagTestDetail, diagTestGoals))
    } catch (e) {
      setDiagKeyword({ success: false, error_type: 'exception', error_message: e.message })
    }
    setDiagRunning('')
  }

  // 字段映射
  const keyConfigured = diagHealth?.api_key_configured === true || diagConfig?.DEEPSEEK_API_KEY_CONFIGURED === true
  const modelDisplay = diagHealth?.display_model || diagHealth?.api_model || diagConfig?.DEEPSEEK_MODEL || '?'
  const statusCode = diagHealth?.last_check?.status_code
  const finishReason = diagHealth?.last_check?.finish_reason
  const connected = statusCode === 200
  const keyMasked = diagConfig?.DEEPSEEK_API_KEY_MASKED || diagHealth?.api_key_masked || ''

  return (
    <section className="tool-page">
      <header className="tool-header">
        <div>
          <div className="section-kicker"><Activity size={16} />模型状态</div>
          <h2>后端模型、检索配置与 DeepSeek 诊断</h2>
        </div>
      </header>
      {error && <div className="notice notice-error">{error}</div>}
      <ModelStatusPanel status={status} />

      {/* DeepSeek 诊断 */}
      <section className="result-block" style={{ marginTop: 20 }}>
        <h3><Zap size={16} /> DeepSeek 诊断测试</h3>
        <div className="form-actions" style={{ gap: 10, flexWrap: 'wrap' }}>
          <button className="secondary-button" onClick={runHealthCheck} disabled={!!diagRunning}>
            {diagRunning === 'health' ? <Loader size={14} className="spin" /> : <Activity size={14} />}
            检查 DeepSeek 健康状态
          </button>
        </div>

        {diagHealth && (
          <div className={`notice ${keyConfigured ? 'notice-ok' : 'notice-error'}`} style={{ marginTop: 8 }}>
            {keyConfigured ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
            <strong>Key:</strong> {keyConfigured ? '已配置' : '未配置'}
            {keyMasked && <> (<code>{keyMasked}</code>)</>}
            {' | '}
            <strong>连通:</strong> {connected ? '成功' : '失败'}
            {' | '}
            <strong>模型:</strong> {modelDisplay}
            {statusCode && <> | <strong>status:</strong> {statusCode}</>}
            {finishReason && <> | <strong>finish:</strong> {finishReason}</>}
            {finishReason === 'length' && <span className="tag tag-warn" style={{ marginLeft: 6 }}>输出被截断</span>}
            {diagHealth.last_error && <><br/><strong>错误:</strong> {diagHealth.last_error}</>}
          </div>
        )}

        {/* 原始 JSON 展示 */}
        {(diagHealth || diagConfig) && (
          <div style={{ marginTop: 8 }}>
            <button
              className="secondary-button"
              style={{ fontSize: '0.8rem', padding: '4px 10px' }}
              onClick={() => setShowRaw(!showRaw)}
            >
              {showRaw ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              查看后端原始返回
            </button>
            {showRaw && (
              <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {diagConfig && (
                  <div style={{ background: '#f5f5f0', padding: 8, borderRadius: 6, fontSize: '0.78rem', maxHeight: 300, overflow: 'auto' }}>
                    <strong>/api/config/runtime</strong>
                    <pre style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{JSON.stringify(diagConfig, null, 2)}</pre>
                  </div>
                )}
                {diagHealth && (
                  <div style={{ background: '#f5f5f0', padding: 8, borderRadius: 6, fontSize: '0.78rem', maxHeight: 300, overflow: 'auto' }}>
                    <strong>/api/deepseek/health</strong>
                    <pre style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{JSON.stringify(diagHealth, null, 2)}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <h4 style={{ marginTop: 16 }}>测试关键词生成</h4>
        <div className="two-column-form" style={{ marginBottom: 8 }}>
          <label>测试案件详情<textarea rows={4} value={diagTestDetail} onChange={e => setDiagTestDetail(e.target.value)} placeholder="输入测试案件详情..." /></label>
          <label>测试希望结果<textarea rows={4} value={diagTestGoals} onChange={e => setDiagTestGoals(e.target.value)} placeholder="输入希望结果（可选）" /></label>
        </div>
        <button className="secondary-button" onClick={runKeywordTest} disabled={!!diagRunning}>
          {diagRunning === 'keyword' ? <Loader size={14} className="spin" /> : <Search size={14} />}
          测试关键词生成
        </button>
        {diagKeyword && (
          <div style={{ marginTop: 12, padding: 12, border: '1px solid #d9dcd4', borderRadius: 8, background: '#fafaf8', fontSize: '0.85rem' }}>
            <div style={{ marginBottom: 8 }}>
              {diagKeyword.success ? <span className="tag tag-ok">成功</span> : <span className="tag tag-danger">失败</span>}
              {' '}<strong>parse:</strong> {diagKeyword.parse_method} |
              <strong> keywords:</strong> {diagKeyword.keyword_count} |
              <strong> raw_length:</strong> {diagKeyword.raw_length}
            </div>
            {diagKeyword.keywords?.length > 0 && (
              <div style={{ marginBottom: 8 }}><strong>关键词:</strong> {diagKeyword.keywords.join(', ')}</div>
            )}
            {diagKeyword.raw_preview && <div style={{ marginBottom: 8, color: '#666', maxHeight: 80, overflow: 'auto' }}><strong>raw:</strong> {diagKeyword.raw_preview}</div>}
            {diagKeyword.deepseek_diagnostics && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 4 }}>
                {Object.entries(diagKeyword.deepseek_diagnostics).map(([k, v]) => (
                  <span key={k}><strong>{k}:</strong> {JSON.stringify(v)}</span>
                ))}
              </div>
            )}
            {diagKeyword.check_suggestions?.length > 0 && (
              <div className="notice notice-warn" style={{ marginTop: 8 }}>
                <strong>检查建议:</strong>
                <ul style={{ margin: '4px 0 0 16px' }}>{diagKeyword.check_suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            )}
          </div>
        )}
      </section>
    </section>
  )
}
