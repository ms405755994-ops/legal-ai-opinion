import { Paperclip, Upload, X, FileText, AlertTriangle, CheckCircle, Loader } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import api from '../api/client.js'

const ALLOWED_TYPES = ['.pdf', '.docx', '.txt', '.md', '.csv', '.json', '.png', '.jpg', '.jpeg']

/**
 * 附件上传组件
 * 
 * Props:
 *   value: 当前案件详情文本
 *   onExtractedText: (text, mode) => void  — 提取完成后回调
 *   disabled: boolean
 */
export default function AttachmentUploader({ value, onExtractedText, disabled }) {
  const [files, setFiles] = useState([])       // 本地文件列表（含状态）
  const [mode, setMode] = useState('append')   // replace | append
  const [uploading, setUploading] = useState(false)
  const [resultMsg, setResultMsg] = useState('')    // 成功/失败提示
  const [msgType, setMsgType] = useState('')        // success | error
  const fileInputRef = useRef(null)
  const dropRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  // ── 文件选择 ──
  const handleSelectFiles = useCallback((selected) => {
    const valid = []
    for (const f of selected) {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase()
      if (!ALLOWED_TYPES.includes(ext)) {
        valid.push({ file: f, status: 'failed', message: `不支持的文件类型 ${ext}` })
      } else if (f.size > 20 * 1024 * 1024) {
        valid.push({ file: f, status: 'failed', message: '文件超过 20 MB 上限' })
      } else {
        valid.push({ file: f, status: 'waiting', message: '等待上传' })
      }
    }
    setFiles(prev => [...prev, ...valid].slice(0, 10))
    setResultMsg('')
  }, [])

  const handleFileChange = (e) => {
    handleSelectFiles(Array.from(e.target.files || []))
    e.target.value = ''
  }

  const removeFile = (idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx))
  }

  // ── 拖拽 ──
  const handleDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }
  const handleDragLeave = () => setDragOver(false)
  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleSelectFiles(Array.from(e.dataTransfer.files || []))
  }

  // ── 上传与提取 ──
  const handleUpload = async () => {
    const waiting = files.filter(f => f.status === 'waiting')
    if (waiting.length === 0) {
      setResultMsg('没有待上传的文件')
      setMsgType('error')
      return
    }

    setUploading(true)
    setResultMsg('')
    setMsgType('')

    // 标记为正在提取
    setFiles(prev => prev.map(f =>
      f.status === 'waiting' ? { ...f, status: 'extracting', message: '正在提取...' } : f
    ))

    const formData = new FormData()
    for (const f of waiting) {
      formData.append('files', f.file)
    }
    formData.append('mode', mode)
    formData.append('use_ai_summary', 'true')

    try {
      const resp = await api.extractAttachments(formData)

      // 更新文件状态
      setFiles(prev => {
        const resultMap = {}
        for (const r of resp.files || []) {
          resultMap[r.filename] = r
        }
        return prev.map(f => {
          const r = resultMap[f.file.name]
          if (r) {
            return {
              ...f,
              status: r.status,
              message: r.message,
              raw_text_length: r.raw_text_length || 0,
              extract_method: r.extract_method || 'none',
              ocr_used: r.ocr_used || false,
              ocr_engine: r.ocr_engine || 'none',
              pages_processed: r.pages_processed || 0,
            }
          }
          return f
        })
      })

      if (resp.success && resp.case_detail_text) {
        onExtractedText(resp.case_detail_text, mode)
        const anyOcr = (resp.files || []).some(f => f.ocr_used)
        const ocrPages = (resp.files || []).reduce((sum, f) => sum + (f.pages_processed || 0), 0)
        if (anyOcr && ocrPages > 0) {
          setResultMsg(`OCR 识别成功，已处理 ${ocrPages} 页。已提取并整理案件信息，建议你检查后再开始深度分析。`)
        } else {
          setResultMsg('已从附件中提取并整理案件信息，建议你检查后再开始深度分析。')
        }
        setMsgType('success')
      } else {
        const failedMessages = (resp.files || [])
          .filter((item) => item.status === 'failed' && item.message)
          .map((item) => item.message)
        setResultMsg(
          resp.warnings?.[0] ||
          failedMessages[0] ||
          '附件上传失败，请确认后端服务已启动。'
        )
        setMsgType('error')
      }
    } catch (err) {
      const msg = err.message || '附件上传失败，请确认后端服务已启动。'
      setResultMsg(msg)
      setMsgType('error')
      setFiles(prev => prev.map(f =>
        f.status === 'extracting' ? { ...f, status: 'failed', message: msg } : f
      ))
    } finally {
      setUploading(false)
    }
  }

  // ── 渲染 ──
  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  const statusIcon = (status) => {
    switch (status) {
      case 'success': return <CheckCircle size={14} className="text-green" />
      case 'failed': return <AlertTriangle size={14} className="text-red" />
      case 'extracting': return <Loader size={14} className="spin text-blue" />
      default: return <FileText size={14} className="text-muted" />
    }
  }

  const fileTypeLabel = (name) => {
    const ext = name.split('.').pop()?.toUpperCase()
    return ext || '?'
  }

  return (
    <div className="attachment-uploader" ref={dropRef}>
      {/* 标题 */}
      <div className="uploader-header">
        <Paperclip size={16} />
        <span>上传案件附件</span>
        <span style={{ color: '#e53e3e', fontSize: '12px', marginLeft: '8px', fontWeight: 'normal' }}>（功能未完善，暂不可用）</span>
      </div>
      <p className="uploader-desc">
        支持上传合同、聊天记录、裁决书、判决书、通知书、证据说明等文件。
        系统会自动提取文字并整理为案件详情，填入下方输入框。
      </p>

      {/* 拖拽区 */}
      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${disabled || uploading ? 'disabled' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && !uploading && fileInputRef.current?.click()}
      >
        <Upload size={20} />
        <span>选择附件（或拖拽文件到此处）</span>
        <span className="drop-hint">支持 PDF / DOCX / TXT / MD / CSV / JSON，单文件最大 20 MB，最多 10 个</span>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ALLOWED_TYPES.join(',')}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {/* 文件列表 */}
      {files.length > 0 && (
        <ul className="file-list">
          {files.map((f, i) => (
            <li key={i} className={`file-item status-${f.status}`}>
              <span className="file-icon">{statusIcon(f.status)}</span>
              <span className="file-name">{f.file.name}</span>
              <span className="file-type-badge">{fileTypeLabel(f.file.name)}</span>
              <span className="file-size">{formatSize(f.file.size)}</span>
              <span className="file-status-text">
                {f.message}
                {f.ocr_used && f.pages_processed > 0 && `（${f.pages_processed} 页）`}
                {f.extract_method === 'ocr' && f.status === 'success' && ' · OCR'}
                {f.extract_method === 'text_layer' && f.status === 'success' && ' · 可复制文字'}
              </span>
              {!uploading && (
                <button className="file-remove" onClick={() => removeFile(i)} title="移除">
                  <X size={12} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* 操作行 */}
      <div className="uploader-actions">
        <div className="mode-switch">
          <span className="mode-label">填入方式：</span>
          <label className={`mode-option ${mode === 'replace' ? 'active' : ''}`}>
            <input
              type="radio"
              name="attach-mode"
              value="replace"
              checked={mode === 'replace'}
              onChange={() => setMode('replace')}
            />
            替换当前内容
          </label>
          <label className={`mode-option ${mode === 'append' ? 'active' : ''}`}>
            <input
              type="radio"
              name="attach-mode"
              value="append"
              checked={mode === 'append'}
              onChange={() => setMode('append')}
            />
            追加到当前内容
          </label>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={disabled || uploading || files.filter(f => f.status === 'waiting').length === 0}
          onClick={handleUpload}
        >
          {uploading ? (
            <><Loader size={14} className="spin" /> 正在提取...</>
          ) : (
            <><Upload size={14} /> 上传并提取文字</>
          )}
        </button>
      </div>

      {/* 结果提示 */}
      {resultMsg && (
        <div className={`upload-result-msg ${msgType}`}>
          {msgType === 'success' ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
          <span>{resultMsg}</span>
        </div>
      )}
    </div>
  )
}
