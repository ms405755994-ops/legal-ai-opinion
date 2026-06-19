import { Globe2, KeyRound, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import api from '../api/client.js'

export default function DataSourceSettingsPage() {
  const [sources, setSources] = useState([])
  const [providerStatus, setProviderStatus] = useState({})
  const [savingId, setSavingId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const [sourcePayload, statusPayload] = await Promise.all([
        api.getOnlineSources(),
        api.providerStatus()
      ])
      setSources(sourcePayload)
      setProviderStatus(statusPayload)
    } catch (err) {
      setError(err.message)
    }
  }

  async function updateSource(id, patch) {
    setError('')
    setSavingId(id)
    try {
      const updated = await api.updateOnlineSource(id, patch)
      setSources((items) => items.map((item) => (item.id === id ? updated : item)))
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingId('')
    }
  }

  const onlineSearchReady = Boolean(providerStatus.ready)
  const provider = providerStatus.provider || 'tavily'

  return (
    <section className="tool-page">
      <header className="tool-header">
        <div>
          <div className="section-kicker"><Globe2 size={16} />数据源设置</div>
          <h2>官方在线来源与搜索 Provider</h2>
        </div>
      </header>

      {error && <div className="notice notice-error">{error}</div>}
      {!onlineSearchReady && (
        <div className="notice notice-warn">
          当前未配置在线搜索 API Key，系统无法自动检索真实案例链接。请在 backend/.env 中配置 Tavily API Key。
        </div>
      )}

      <section className="provider-panel">
        <div className="provider-title">
          <KeyRound size={17} />
          <strong>搜索 Provider 配置</strong>
        </div>
        <dl>
          <div><dt>当前 Provider</dt><dd>{provider}</dd></div>
          <div>
            <dt>配置状态</dt>
            <dd>
              {onlineSearchReady
                ? <span className="tag tag-ok">已配置 API Key / 在线搜索可用</span>
                : <span className="tag">未配置 API Key</span>
              }
            </dd>
          </div>
          <div><dt>配置位置</dt><dd>backend/.env</dd></div>
          {providerStatus.message && (
            <div><dt>状态消息</dt><dd className="muted">{providerStatus.message}</dd></div>
          )}
        </dl>
      </section>

      <section className="source-list online-source-list">
        <h3>官方在线来源白名单</h3>
        {sources.map((item) => (
          <article className="online-source-card" key={item.id}>
            <div>
              <div className="source-card-head">
                <strong>{item.name}</strong>
                <span className={item.enabled ? 'tag tag-ok' : 'tag'}>{item.enabled ? '启用' : '停用'}</span>
              </div>
              <p className="muted">{item.note}</p>
              <dl className="source-meta">
                <div><dt>域名</dt><dd>{item.domain}</dd></div>
                <div><dt>类型</dt><dd>{item.source_type}</dd></div>
                <div><dt>搜索前缀</dt><dd>{item.search_query_prefix}</dd></div>
              </dl>
            </div>
            <div className="source-controls">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(item.enabled)}
                  disabled={savingId === item.id}
                  onChange={(event) => updateSource(item.id, { enabled: event.target.checked })}
                />
                启用
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(item.allow_online_index_search)}
                  disabled={savingId === item.id}
                  onChange={(event) => updateSource(item.id, { allow_online_index_search: event.target.checked })}
                />
                允许在线索引搜索
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(item.allow_direct_fetch)}
                  disabled={savingId === item.id}
                  onChange={(event) => updateSource(item.id, { allow_direct_fetch: event.target.checked })}
                />
                允许直接访问公开页面
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(item.stop_if_login_or_captcha)}
                  disabled={savingId === item.id}
                  onChange={(event) => updateSource(item.id, { stop_if_login_or_captcha: event.target.checked })}
                />
                遇到登录/验证码就停止
              </label>
              {savingId === item.id && <span className="muted"><Save size={14} />保存中</span>}
            </div>
          </article>
        ))}
      </section>
    </section>
  )
}
