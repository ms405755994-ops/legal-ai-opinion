import { Download, FileText } from 'lucide-react'
import { marked } from 'marked'
import { useMemo, useState } from 'react'
import api from '../api/client.js'
import CaseCard from './CaseCard.jsx'
import RiskPanel from './RiskPanel.jsx'

export default function ResultViewer({ result }) {
  const [downloadError, setDownloadError] = useState('')
  const [working, setWorking] = useState(false)
  const html = useMemo(() => marked.parse(result.markdown || ''), [result.markdown])

  async function downloadWord() {
    setDownloadError('')
    setWorking(true)
    try {
      let fileId = result.docx_file_id
      if (!fileId) {
        const exported = await api.exportDocx(result.markdown, result.cases || [], result.analysis_id)
        fileId = exported.file_id
      }
      // 使用带 Authorization 令牌的下载方式
      const blob = await api.downloadFile(fileId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileId.endsWith('.docx') ? fileId : `${fileId}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setDownloadError(err.message)
    } finally {
      setWorking(false)
    }
  }

  return (
    <section className="result-section">
      <header className="result-header">
        <div>
          <div className="section-kicker">
            <FileText size={16} />
            分析报告
          </div>
          <h2>类案检索与案件处理思路</h2>
        </div>
      </header>

      {downloadError && <div className="notice notice-error">{downloadError}</div>}
      {result.can_be_used_for_real_case === false && (
        <div className="notice notice-danger">
          当前报告不可用于真实案件，仅用于系统测试。
        </div>
      )}
      <div className="mode-summary">
        <span>案例模式：{result.case_mode || 'mock'}</span>
        <span>真实在线链接：{result.real_case_count ?? 0}</span>
        <span>已核验：{result.verified_case_count ?? 0}</span>
        <span>待核验：{result.unverified_case_count ?? 0}</span>
        <span>MOCK 案例：{result.mock_case_count ?? 0}</span>
      </div>
      {result.search_summary && (
        <section className="search-summary">
          <h3>自动检索摘要</h3>
          <dl>
            <div><dt>搜索 Provider</dt><dd>{result.search_summary.provider || '-'}</dd></div>
            <div><dt>Provider 状态</dt><dd>{result.search_summary.provider_ready ? '已配置' : '未配置'}</dd></div>
            <div><dt>生成关键词数量</dt><dd>{(result.keywords || []).length}</dd></div>
            <div><dt>搜索 Query 数量</dt><dd>{result.search_summary.total_queries ?? 0}</dd></div>
            <div><dt>原始结果数量</dt><dd>{result.search_summary.total_raw_results ?? 0}</dd></div>
            <div><dt>官方来源结果数量</dt><dd>{result.search_summary.official_results ?? 0}</dd></div>
            <div><dt>AI 判断链接数量</dt><dd>{result.search_summary.links_judged ?? 0}</dd></div>
            <div><dt>有用链接数量</dt><dd>{result.search_summary.useful_links ?? 0}</dd></div>
            <div><dt>本报告引用链接数量</dt><dd>{result.search_summary.used_in_report ?? 0}</dd></div>
          </dl>
        </section>
      )}

      <section className="result-block output-block">
        <h3>相关案例链接</h3>
        {(result.cases || []).length === 0 && <p className="muted">未找到可核验真实案例链接。</p>}
        <section className="case-grid">
          {(result.cases || []).map((item) => (
            <CaseCard item={item} key={item.id || item.case_no || item.title} />
          ))}
        </section>
      </section>
      <section className="result-block output-block">
        <h3>处理思路</h3>
        <article className="markdown-report" dangerouslySetInnerHTML={{ __html: html }} />
      </section>
      <section className="result-block output-block">
        <RiskPanel review={result.review} warnings={result.warnings} />
      </section>
      <section className="result-block output-block download-block">
        <div>
          <h3>Word 下载</h3>
          <p className="muted">下载当前网页报告对应的 Word 文件。</p>
        </div>
        <button className="primary-button" type="button" onClick={downloadWord} disabled={working}>
          <Download size={17} />
          {working ? '生成中' : '下载 Word'}
        </button>
      </section>
    </section>
  )
}
