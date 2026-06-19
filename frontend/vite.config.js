import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages 部署：如果仓库名为 legal-ai-opinion，base 应为 "/legal-ai-opinion/"
// 如果使用自定义域名，可改为 "/"
const GITHUB_PAGES_BASE = '/legal-ai-opinion/'

export default defineConfig({
  plugins: [react()],
  base: GITHUB_PAGES_BASE,
  server: {
    host: '127.0.0.1',
    port: 5173
  }
})
