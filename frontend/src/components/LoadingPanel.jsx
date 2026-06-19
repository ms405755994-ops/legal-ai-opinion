import React from 'react'

/**
 * 加载面板 —— 显示分析进度
 */
export default function LoadingPanel({ visible }) {
  if (!visible) return null

  return (
    <div className="loading-panel">
      <div className="loading-spinner"></div>
      <div className="loading-text">
        <h3>🤖 AI 正在深度分析中...</h3>
        <p className="loading-steps">
          <span className="step active">✓ 拆解案件事实</span>
          <span className="step active">✓ 分析法律路径</span>
          <span className="step">⏳ 检索类似案例</span>
          <span className="step">⏳ 生成处理方案</span>
          <span className="step">⏳ 生成 Word 报告</span>
        </p>
        <p className="loading-note">
          深度分析可能需要 30-120 秒，请耐心等待...
        </p>
      </div>
    </div>
  )
}
