import React, { useState, useEffect, useCallback } from 'react'
import api from '../api/client.js'

/**
 * 数据源设置弹窗
 */
export default function SourceSettingsModal({ visible, onClose }) {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(null)   // 正在编辑的 source id
  const [form, setForm] = useState({ id: '', name: '', url: '', type: 'other', enabled: true, note: '' })

  // 加载数据源列表
  const loadSources = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getSources()
      setSources(data)
    } catch (err) {
      alert('加载数据源失败：' + err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (visible) loadSources()
  }, [visible, loadSources])

  // 新增
  const handleCreate = async () => {
    if (!form.id || !form.name || !form.url) {
      alert('ID、名称和 URL 为必填项')
      return
    }
    try {
      await api.createSource(form)
      setForm({ id: '', name: '', url: '', type: 'other', enabled: true, note: '' })
      loadSources()
    } catch (err) {
      alert('新增失败：' + err.message)
    }
  }

  // 更新
  const handleUpdate = async (id) => {
    try {
      await api.updateSource(id, form)
      setEditing(null)
      setForm({ id: '', name: '', url: '', type: 'other', enabled: true, note: '' })
      loadSources()
    } catch (err) {
      alert('更新失败：' + err.message)
    }
  }

  // 删除
  const handleDelete = async (id) => {
    if (!confirm(`确定删除数据源 "${id}"？`)) return
    try {
      await api.deleteSource(id)
      loadSources()
    } catch (err) {
      alert('删除失败：' + err.message)
    }
  }

  // 开始编辑
  const startEdit = (source) => {
    setEditing(source.id)
    setForm({ ...source })
  }

  // 取消编辑
  const cancelEdit = () => {
    setEditing(null)
    setForm({ id: '', name: '', url: '', type: 'other', enabled: true, note: '' })
  }

  if (!visible) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>⚙️ 数据源设置</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {/* 新增 / 编辑表单 */}
          <div className="source-form">
            <h3>{editing ? '编辑数据源' : '新增数据源'}</h3>
            <div className="form-row">
              <input
                placeholder="ID（英文标识）"
                value={form.id}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                disabled={!!editing}
              />
              <input
                placeholder="名称"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="form-row">
              <input
                placeholder="URL"
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
              />
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                <option value="official_case_library">官方案例库</option>
                <option value="judgment_database">裁判文书库</option>
                <option value="commercial_database">商业数据库</option>
                <option value="other">其他</option>
              </select>
            </div>
            <div className="form-row">
              <input
                placeholder="备注说明"
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
              />
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                启用
              </label>
            </div>
            <div className="form-actions">
              {editing ? (
                <>
                  <button className="btn btn-primary" onClick={() => handleUpdate(editing)}>保存修改</button>
                  <button className="btn btn-secondary" onClick={cancelEdit}>取消</button>
                </>
              ) : (
                <button className="btn btn-primary" onClick={handleCreate}>新增</button>
              )}
            </div>
          </div>

          {/* 数据源列表 */}
          <div className="source-list">
            <h3>当前数据源 ({sources.length})</h3>
            {loading && <p>加载中...</p>}
            {sources.map((s) => (
              <div key={s.id} className={`source-item ${s.enabled ? '' : 'disabled'}`}>
                <div className="source-info">
                  <strong>{s.name}</strong>
                  <span className="source-id">{s.id}</span>
                  <span className="source-type">{s.type}</span>
                  <span className={`source-status ${s.enabled ? 'enabled' : ''}`}>
                    {s.enabled ? '✅ 启用' : '⛔ 禁用'}
                  </span>
                  <p className="source-url">{s.url}</p>
                  {s.note && <p className="source-note">{s.note}</p>}
                </div>
                <div className="source-actions">
                  <button className="btn btn-sm" onClick={() => startEdit(s)}>编辑</button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(s.id)}>删除</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
