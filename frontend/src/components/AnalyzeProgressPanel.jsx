import { AlertTriangle, CheckCircle, Clock, Loader, XCircle, XOctagon } from 'lucide-react'
import { useEffect, useRef } from 'react'

const STEP_LABELS = [
  { key: 'analyzing_case', label: '案件拆解' },
  { key: 'generating_keywords', label: '生成关键词' },
  { key: 'searching_official_sources', label: '搜索官方来源' },
  { key: 'filtering_official_links', label: '筛选官方链接' },
  { key: 'judging_links', label: 'AI 判断链接' },
  { key: 'generating_report', label: '生成处理思路' },
  { key: 'generating_word', label: '生成 Word' },
]

const STEP_KEYS = STEP_LABELS.map((s) => s.key)

export default function AnalyzeProgressPanel({ progress, onCancel, cancelled }) {
  const logEndRef = useRef(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [progress?.logs?.length])

  if (!progress) return null

  const { status, current_step, current_step_label, step_index, total_steps, percent, elapsed_seconds, logs, metrics, error } = progress

  const formatTime = (sec) => {
    if (sec < 60) return `${sec} 秒`
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m} 分 ${s} 秒`
  }

  const currentStepIdx = STEP_KEYS.indexOf(current_step)

  return (
    <section className="progress-panel" aria-live="polite">
      {/* 状态头 */}
      <div className="progress-header">
        <div className="progress-status-row">
          {status === 'running' && <Loader size={20} className="spin text-blue" />}
          {status === 'completed' && <CheckCircle size={20} className="text-green" />}
          {status === 'failed' && <XCircle size={20} className="text-red" />}
          {status === 'cancelled' && <XOctagon size={20} className="text-red" />}
          <span className="progress-status-text">{current_step_label || '正在初始化'}</span>
          <span className="progress-eta">
            <Clock size={14} /> 已耗时 {formatTime(elapsed_seconds)}
          </span>
        </div>

        {/* 进度条 */}
        <div className="progress-bar-track">
          <div
            className={`progress-bar-fill ${status === 'failed' ? 'failed' : ''} ${status === 'cancelled' ? 'cancelled' : ''}`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
          <span className="progress-bar-text">{percent}%</span>
        </div>
      </div>

      {/* 步骤卡片 */}
      <div className="progress-steps">
        {STEP_LABELS.map((step, idx) => {
          let stepStatus = 'pending'
          if (idx < currentStepIdx) stepStatus = 'done'
          else if (idx === currentStepIdx && status === 'running') stepStatus = 'active'
          else if (idx === currentStepIdx && status === 'completed') stepStatus = 'done'
          else if (idx === currentStepIdx && status === 'failed') stepStatus = 'error'
          else stepStatus = 'pending'

          return (
            <div key={step.key} className={`progress-step-card ${stepStatus}`}>
              <span className="step-num">
                {stepStatus === 'done' ? <CheckCircle size={14} /> :
                 stepStatus === 'active' ? <Loader size={14} className="spin" /> :
                 stepStatus === 'error' ? <XCircle size={14} /> : idx + 1}
              </span>
              <span className="step-label">{step.label}</span>
              <span className="step-status-text">
                {stepStatus === 'done' ? '已完成' :
                 stepStatus === 'active' ? '进行中' :
                 stepStatus === 'error' ? '失败' : '等待中'}
              </span>
            </div>
          )
        })}
      </div>

      {/* 统计指标 */}
      {metrics && Object.keys(metrics).length > 0 && (
        <div className="progress-metrics">
          {metrics.keywords_count !== undefined && (
            <div className="metric-item"><strong>{metrics.keywords_count}</strong> 关键词</div>
          )}
          {metrics.sources_count !== undefined && (
            <div className="metric-item"><strong>{metrics.sources_count}</strong> 官方来源</div>
          )}
          {metrics.queries_count !== undefined && metrics.queries_done_count !== undefined && (
            <div className="metric-item"><strong>{metrics.queries_done_count} / {metrics.queries_count}</strong> 搜索进度</div>
          )}
          {metrics.raw_results_count !== undefined && (
            <div className="metric-item"><strong>{metrics.raw_results_count}</strong> 搜索结果</div>
          )}
          {metrics.official_results_count !== undefined && (
            <div className="metric-item"><strong>{metrics.official_results_count}</strong> 官方来源</div>
          )}
          {metrics.links_judged_count !== undefined && (
            <div className="metric-item"><strong>{metrics.links_judged_count}</strong> 已判断</div>
          )}
          {metrics.batches_total !== undefined && metrics.batches_done !== undefined && (
            <div className="metric-item"><strong>{metrics.batches_done} / {metrics.batches_total}</strong> 批次</div>
          )}
          {metrics.avg_batch_seconds !== undefined && (
            <div className="metric-item"><strong>{metrics.avg_batch_seconds}s</strong> 平均每批</div>
          )}
          {metrics.useful_links_count !== undefined && (
            <div className="metric-item"><strong>{metrics.useful_links_count}</strong> 有用链接</div>
          )}
          {metrics.used_links_count !== undefined && (
            <div className="metric-item"><strong>{metrics.used_links_count}</strong> 报告引用</div>
          )}
        </div>
      )}

      {/* 实时日志 */}
      {logs && logs.length > 0 && (
        <div className="progress-logs">
          <h4>实时日志</h4>
          <div className="log-container">
            {logs.map((entry, i) => (
              <div key={i} className={`log-entry log-${entry.level || 'info'} ${i === logs.length - 1 ? 'log-latest' : ''}`}>
                <span className="log-time">{entry.time}</span>
                <span className="log-msg">{entry.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* 错误信息 */}
      {error && (
        <div className="notice notice-error">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* 取消按钮 */}
      {status === 'running' && !cancelled && (
        <div className="progress-cancel-row">
          <button className="secondary-button" type="button" onClick={onCancel}>
            <XOctagon size={16} /> 取消分析
          </button>
        </div>
      )}

      {cancelled && (
        <div className="notice notice-warn">分析已取消</div>
      )}
    </section>
  )
}
