import React from 'react'

/**
 * 期望目标输入组件 —— 右侧文本框
 */
export default function GoalInput({ value, onChange, disabled }) {
  return (
    <div className="goal-input">
      <label className="input-label">
        🎯 期望达成的目标
        <span className="label-hint">多个期望值用中文逗号（，）或英文逗号（,）分隔</span>
      </label>
      <textarea
        className="input-textarea goal-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`请在此输入您期望达成的目标，多个目标用逗号分隔，例如：

退货退款，赔偿损失，解除合同，支付违约金`}
        rows={16}
        disabled={disabled}
      />
      <div className="goal-pills">
        {value
          .split(/[，,]/)
          .filter((g) => g.trim())
          .map((goal, i) => (
            <span key={i} className="goal-pill">
              {goal.trim()}
            </span>
          ))}
      </div>
    </div>
  )
}
