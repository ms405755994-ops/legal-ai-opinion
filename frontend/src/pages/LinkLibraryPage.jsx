import { Link, Search, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import api from '../api/client.js'

export default function LinkLibraryPage() {
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getOnlineSources().then(data => {
      setLinks(Array.isArray(data) ? data : [])
    }).catch(err => {
      setError(err.message)
    }).finally(() => setLoading(false))
  }, [])

  async function handleDelete(id) {
    try {
      await api.deleteSource(id)
      setLinks(prev => prev.filter(l => l.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="notice">加载中……</div>

  return (
    <section className="link-library">
      <div className="section-kicker">
        <Link size={16} />
        自动检索结果库
      </div>
      {error && <div className="notice notice-error">{error}</div>}
      {links.length === 0 ? (
        <p className="notice">暂无自动检索到的案例链接。进行一键深度分析后，自动检索到的有用链接会出现在这里。</p>
      ) : (
        <ul className="link-list">
          {links.map(link => (
            <li key={link.id || link.url} className="link-row">
              <div className="source-main">
                <strong>{link.title || link.url}</strong>
                {link.url && (
                  <a href={link.url} target="_blank" rel="noopener noreferrer">
                    <Search size={14} /> {link.url}
                  </a>
                )}
              </div>
              <div className="link-meta">
                {link.verified ? <span className="tag tag-ok">已核验</span> : <span className="tag tag-warn">待核验</span>}
              </div>
              <button className="file-remove" onClick={() => handleDelete(link.id)} title="删除">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
