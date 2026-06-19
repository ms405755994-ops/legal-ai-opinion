import React from 'react'

/**
 * 案件详情输入组件 —— 左侧大文本框
 */
export default function CaseInput({ value, onChange, disabled }) {
  return (
    <div className="case-input">
      <label className="input-label">
        📋 当前案件详情
        <span className="label-hint">请输入案件的事实经过、涉及主体、时间节点等详细信息</span>
      </label>
      <textarea
        className="input-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`请在此输入当前案件的详细情况，例如：

案件事实：
2024年6月，我方与XX公司签订购销合同，约定……
对方于2024年8月交付货物，但货物存在以下质量问题……

涉及主体：
甲方（我方）：XX公司
乙方（对方）：XX公司

争议金额：人民币XX元

目前已采取的救济措施：
1. 已发送书面催告函
2. 已委托第三方检测……`}
        rows={16}
        disabled={disabled}
      />
    </div>
  )
}
