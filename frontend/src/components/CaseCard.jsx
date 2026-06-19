import { ExternalLink, Gavel, Scale } from 'lucide-react'

const typeLabels = {
  case: '案例',
  statute: '法规',
  policy: '政策',
  unknown: '其他'
}

export default function CaseCard({ item }) {
  const caseNo = item.case_no || item.id || ''
  const title = item.title || '未知标题'
  const url = item.url || item.link || ''
  const resultType = item.result_type || item.type || 'unknown'
  const matchedGoal = item.matched_goal || ''
  const usefulScore = item.useful_score != null ? item.useful_score : (item.score != null ? item.score : 0)
  const verified = item.verified === true

  return (
    <article className={`case-card ${verified ? 'verified' : ''}`}>
      <div className="case-card-head">
        <span className={`tag ${verified ? 'tag-ok' : 'tag-warn'}`}>
          {verified ? <Scale size={14} /> : <Gavel size={14} />}
          {verified ? '已核验' : '待核验'}
        </span>
        <span className="tag">{typeLabels[resultType] || resultType}</span>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" className="case-link-icon">
            <ExternalLink size={14} />
          </a>
        )}
      </div>
      <h4 className="case-card-title">{title}</h4>
      {caseNo && <p className="case-card-no">{caseNo}</p>}
      {matchedGoal && <p className="case-card-goal">匹配目标：{matchedGoal}</p>}
      {usefulScore > 0 && (
        <div className="case-card-score">
          <span className="score-bar" style={{ width: `${Math.round(usefulScore * 100)}%` }} />
          <span className="score-text">相关性 {(usefulScore * 100).toFixed(0)}%</span>
        </div>
      )}
    </article>
  )
}
