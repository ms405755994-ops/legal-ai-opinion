import { CircleCheck, CircleDashed } from 'lucide-react'

const labels = {
  deepseek: 'DeepSeek',
  lawformer: 'Lawformer',
  disc_lawllm: 'DISC-LawLLM',
  internlm_law: 'InternLM-Law',
  online_search: '在线索引检索'
}

export default function ModelStatusPanel({ status }) {
  return (
    <section className="status-grid">
      {Object.entries(status || {}).map(([key, item]) => {
        const Icon = item.enabled ? CircleCheck : CircleDashed
        return (
          <article className="status-item" key={key}>
            <div className="status-title">
              <Icon size={17} />
              <strong>{labels[key] || key}</strong>
            </div>
            <div className="status-meta">
              <span>{item.role}</span>
              <code>{item.enabled ? item.mode : `mock / ${item.mode}`}</code>
            </div>
          </article>
        )
      })}
    </section>
  )
}
