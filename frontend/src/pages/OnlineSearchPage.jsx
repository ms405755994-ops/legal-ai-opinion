import { CheckCircle2, ExternalLink, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import api from '../api/client.js'
import AttachmentUploader from '../components/AttachmentUploader.jsx'
import CasePresetsBar from '../components/CasePresetsBar.jsx'

export default function OnlineSearchPage() {
  const [caseDetail, setCaseDetail] = useState('')
  const [goals, setGoals] = useState('')
  const [provider, setProvider] = useState('tavily')
  const [sources, setSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([])
  const [keywordResult, setKeywordResult] = useState(null)
  const [collectResult, setCollectResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getOnlineSources().then((items) => {
      setSources(items)
      setSelectedSources(items.filter((item) => item.enabled).map((item) => item.id))
    }).catch((err) => setError(err.message))
  }, [])

  const canRun = useMemo(() => caseDetail.trim() && goals.trim(), [caseDetail, goals])

  function handleExtractedText(text, mode) {
    if (mode === 'replace' || !caseDetail.trim()) {
      setCaseDetail(text)
    } else {
      setCaseDetail(prev => prev + '\n\n' + text)
    }
  }

  function handleFillPreset(text, presetGoals) {
    if (caseDetail.trim() || goals.trim()) {
      if (!window.confirm('当前案件详情或希望结果已有内容，是否替换为预设案例？')) return
    }
    setCaseDetail(text)
    if (presetGoals) setGoals(presetGoals)
  }

  async function previewKeywords() {
    setError('')
    if (!canRun) return setError('请输入案件详情和期望结果')
    setLoading(true)
    try {
      setKeywordResult(await api.previewOnlineKeywords({ case_detail: caseDetail, goals }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function collect() {
    setError('')
    if (!canRun) return setError('请输入案件详情和期望结果')
    setLoading(true)
    try {
      const payload = {
        case_detail: caseDetail,
        goals,
        provider,
        sources: selectedSources,
        max_keywords_per_goal: 8,
        max_results_per_keyword: 10,
        max_links_to_judge: 30,
        max_links_to_store: 10
      }
      const data = await api.collectOnlineLinks(payload)
      setKeywordResult({ keywords: data.keywords, keyword_groups: data.keyword_groups, warnings: data.warnings })
      setCollectResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function toggleSource(id) {
    setSelectedSources((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  async function markVerified(linkId) {
    await api.updateCaseLink(linkId, { verified: true })
    setCollectResult((current) => ({
      ...current,
      stored_links: current.stored_links.map((item) => item.id === linkId ? { ...item, verified: true } : item)
    }))
  }

  return (
    <section className="tool-page">
      <header className="tool-header">
        <div>
          <div className="section-kicker"><Search size={16} />在线索引检索</div>
          <h2>在线检索调试</h2>
        </div>
      </header>
      <section className="notice">
        该页面仅用于测试搜索 API、关键词、数据源和链接筛选效果。正式分析请直接使用“主分析”页面。
      </section>
      <div className="two-column-form">
        <div className="case-input-group">
          <CasePresetsBar
            currentValue={caseDetail}
            goalsValue={goals}
            onFillPreset={handleFillPreset}
            disabled={loading}
          />
          <AttachmentUploader
            value={caseDetail}
            onExtractedText={handleExtractedText}
            disabled={loading}
          />
          <label>
            案件详情
            <textarea value={caseDetail} onChange={(event) => setCaseDetail(event.target.value)} rows={8} />
          </label>
        </div>
        <label>
          期望结果
          <textarea value={goals} onChange={(event) => setGoals(event.target.value)} rows={8} />
        </label>
      </div>
      <div className="control-row">
        <label>
          搜索 Provider
          <select value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="tavily">Tavily（推荐）</option>
            <option value="google_cse">Google CSE</option>
            <option value="bing">Bing（Legacy）</option>
          </select>
        </label>
      </div>
      <section className="source-checkboxes">
        {sources.map((source) => (
          <label key={source.id}>
            <input
              type="checkbox"
              checked={selectedSources.includes(source.id)}
              onChange={() => toggleSource(source.id)}
            />
            {source.name}
            <code>{source.domain}</code>
          </label>
        ))}
      </section>
      {error && <div className="notice notice-error">{error}</div>}
      <div className="form-actions">
        <button className="secondary-button" type="button" onClick={previewKeywords} disabled={loading}>
          <Sparkles size={16} />AI 关键词预览
        </button>
        <button className="primary-button" type="button" onClick={collect} disabled={loading}>
          <Search size={16} />开始在线检索
        </button>
      </div>
      {keywordResult && <KeywordPreview data={keywordResult} />}
      {collectResult && <CollectResult data={collectResult} onVerify={markVerified} />}
    </section>
  )
}

function KeywordPreview({ data }) {
  return (
    <section className="result-block">
      <h3>AI 关键词预览</h3>
      <div className="keyword-list">
        {(data.keywords || []).map((item) => <span key={item}>{item}</span>)}
      </div>
      {(data.warnings || []).map((item) => <p className="muted" key={item}>{item}</p>)}
    </section>
  )
}

function CollectResult({ data, onVerify }) {
  return (
    <section className="result-block">
      <h3>搜索结果</h3>
      <p className="muted">搜索结果 {data.search_results?.length || 0} 条，AI 判断 {data.judged_links?.length || 0} 条，保存 {data.stored_links?.length || 0} 条。</p>
      <h3>已保存链接</h3>
      <div className="link-list">
        {(data.stored_links || []).map((item) => (
          <article className="link-row" key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.source_name} · 分数 {item.useful_score}</p>
              <a href={item.url} target="_blank" rel="noreferrer"><ExternalLink size={14} />{item.url}</a>
            </div>
            <button className="secondary-button" type="button" onClick={() => onVerify(item.id)}>
              <CheckCircle2 size={16} />标记已核验
            </button>
          </article>
        ))}
      </div>
      {(data.skipped || []).length > 0 && <h3>跳过原因</h3>}
      {(data.skipped || []).map((item, index) => (
        <p className="muted" key={`${item.url}-${index}`}>{item.url || '未知链接'}：{item.reason}</p>
      ))}
      {(data.warnings || []).map((item) => <div className="notice notice-error" key={item}>{item}</div>)}
    </section>
  )
}
