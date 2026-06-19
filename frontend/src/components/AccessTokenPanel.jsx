import { Key, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { clearAccessToken, getMaskedToken, hasAccessToken, setAccessToken } from '../api/client.js'

export default function AccessTokenPanel() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [saved, setSaved] = useState(false)
  const [masked, setMasked] = useState('')

  // 同步外部 token 变化
  useEffect(() => {
    setSaved(hasAccessToken())
    setMasked(getMaskedToken())
  }, [])

  function handleSave() {
    const token = input.trim()
    if (!token) return
    setAccessToken(token)
    setInput('')
    setSaved(true)
    setMasked(getMaskedToken())
    setOpen(false)
  }

  function handleClear() {
    clearAccessToken()
    setInput('')
    setSaved(false)
    setMasked('')
    setOpen(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') setOpen(false)
  }

  return (
    <>
      <button
        className={`backend-pill token-btn ${saved ? 'ok' : ''}`}
        type="button"
        title={saved ? `令牌已设置：${masked}` : '设置访问令牌'}
        onClick={() => {
          setOpen(!open)
          setSaved(hasAccessToken())
          setMasked(getMaskedToken())
        }}
      >
        <Key size={14} />
        {saved ? `令牌 ${masked}` : '未设置令牌'}
      </button>

      {open && (
        <div className="token-modal-overlay" onClick={() => setOpen(false)}>
          <dialog
            className="token-modal"
            open
            onClick={(e) => e.stopPropagation()}
            onKeyDown={handleKeyDown}
          >
            <div className="modal-header">
              <h2>访问令牌</h2>
              <button className="pill-btn" type="button" onClick={() => setOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="token-modal-body">
              <p className="token-hint">
                输入与后端 <code>APP_ACCESS_TOKEN</code> 一致的访问令牌。
                令牌仅保存在当前浏览器本地，不会上传到任何服务器。
              </p>

              {saved && (
                <p className="token-status-ok">
                  已设置：<code>{masked}</code>
                </p>
              )}

              <label className="token-label" htmlFor="token-input">访问令牌</label>
              <div className="token-input-row">
                <input
                  id="token-input"
                  className="token-input"
                  type="password"
                  placeholder="输入访问令牌……"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  autoFocus
                />
                <button className="pill-btn primary" type="button" onClick={handleSave} disabled={!input.trim()}>
                  保存
                </button>
              </div>

              {saved && (
                <button className="pill-btn danger" type="button" onClick={handleClear} style={{ marginTop: 8 }}>
                  清除令牌
                </button>
              )}
            </div>
          </dialog>
        </div>
      )}
    </>
  )
}
