import { Bookmark } from 'lucide-react'
import { casePresets } from '../data/casePresets.js'

export default function CasePresetsBar({ currentValue, goalsValue, onFillPreset, disabled }) {
  if (!casePresets || casePresets.length === 0) return null

  function handleClick(preset) {
    const hasContent = (currentValue && currentValue.trim()) || (goalsValue && goalsValue.trim())
    if (hasContent) {
      if (!window.confirm(
        `当前案件详情或希望结果已有内容，是否使用"${preset.name}"替换当前内容？`
      )) {
        return
      }
    }
    onFillPreset(preset.caseDetail, preset.goals || '', preset.name)
  }

  return (
    <div className="case-presets-bar">
      <span className="presets-label">
        <Bookmark size={12} />
        快捷案例：
      </span>
      {casePresets.map((preset) => (
        <button
          key={preset.id}
          className="preset-tag"
          type="button"
          disabled={disabled}
          onClick={() => handleClick(preset)}
          title={`填入${preset.name}`}
        >
          {preset.name}
        </button>
      ))}
    </div>
  )
}
