import { Activity } from 'lucide-react'
import { useEffect, useState } from 'react'
import api from '../api/client.js'
import AccessTokenPanel from '../components/AccessTokenPanel.jsx'
import DataSourceSettingsPage from './DataSourceSettingsPage.jsx'
import LinkLibraryPage from './LinkLibraryPage.jsx'
import MainAnalysisPage from './MainAnalysisPage.jsx'
import ModelStatusPage from './ModelStatusPage.jsx'
import OnlineSearchPage from './OnlineSearchPage.jsx'

const tabs = [
  { id: 'analysis', label: '主分析' },
  { id: 'sources', label: '数据源设置' },
  { id: 'models', label: '模型状态' },
  { id: 'links', label: '自动检索结果库' },
  { id: 'online', label: '高级调试' }
]

export default function AnalyzePage() {
  const [active, setActive] = useState('analysis')
  const [health, setHealth] = useState(null)
  const [status, setStatus] = useState({})

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.modelStatus().then(setStatus).catch(() => setStatus({}))
  }, [])

  const deepseekReady = Boolean(status.deepseek?.enabled)
  const onlineReady = Boolean(status.online_search?.enabled)

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand-line">
            <Activity size={18} />
            legal-ai-opinion
          </div>
          <h1>AI 类案检索助手</h1>
        </div>
        <div className="topbar-actions">
          <AccessTokenPanel />
          <span className={health ? 'backend-pill ok' : 'backend-pill'}>
            后端 {health ? 'OK' : '未连接'}
          </span>
          <span className={deepseekReady ? 'backend-pill ok' : 'backend-pill'}>
            DeepSeek {deepseekReady ? '已启用' : '未启用'}
          </span>
          <span className={onlineReady ? 'backend-pill ok' : 'backend-pill'}>
            在线搜索{onlineReady ? '已配置' : '未配置'}
          </span>
        </div>
      </header>
      <nav className="app-tabs" aria-label="功能菜单">
        {tabs.map((tab) => (
          <button key={tab.id} className={active === tab.id ? 'active' : ''} type="button" onClick={() => setActive(tab.id)}>
            {tab.label}
          </button>
        ))}
      </nav>
      <main className="workspace">
        {active === 'analysis' && <MainAnalysisPage />}
        {active === 'online' && <OnlineSearchPage />}
        {active === 'links' && <LinkLibraryPage />}
        {active === 'sources' && <DataSourceSettingsPage />}
        {active === 'models' && <ModelStatusPage />}
      </main>
    </div>
  )
}
