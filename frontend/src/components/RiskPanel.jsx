import { AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react'

export default function RiskPanel({ review, warnings }) {
  const risks = review?.risks || review?.risk_items || []
  const summary = review?.summary || review?.risk_summary || ''

  return (
    <div className="risk-panel">
      <h3 className="risk-title">
        <ShieldAlert size={18} />
        法律风险提示
      </h3>

      {summary && (
        <p className="risk-summary">{summary}</p>
      )}

      {risks.length > 0 && (
        <ul className="risk-list">
          {risks.map((risk, i) => (
            <li key={i} className="risk-item">
              <div className="risk-item-head">
                {risk.severity === 'high' ? (
                  <AlertTriangle size={14} className="text-red" />
                ) : (
                  <CheckCircle size={14} className="text-green" />
                )}
                <strong>{risk.title || risk.name || `风险项 ${i + 1}`}</strong>
                {risk.severity && (
                  <span className={`tag ${risk.severity === 'high' ? 'tag-danger' : 'tag-warn'}`}>
                    {risk.severity === 'high' ? '高风险' : '中低风险'}
                  </span>
                )}
              </div>
              {risk.description && <p className="risk-desc">{risk.description}</p>}
            </li>
          ))}
        </ul>
      )}

      {warnings && warnings.length > 0 && (
        <div className="risk-warnings">
          <h4>其他提示</h4>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{typeof w === 'string' ? w : w.message || w.text || ''}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
