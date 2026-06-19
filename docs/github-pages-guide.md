# GitHub Pages 部署指南

## 部署原理

前端使用 Vite 构建纯静态文件，部署到 GitHub Pages 后，**前端仍然请求用户本机的 `http://127.0.0.1:8000` 后端**。

```
┌─────────────────────────┐       HTTP (127.0.0.1:8000)       ┌──────────────────────┐
│  GitHub Pages (静态)     │ ─────────────────────────────────> │  本机 FastAPI 后端    │
│  https://xxx.github.io   │                                   │  127.0.0.1:8000      │
│                          │ <───────────────────────────────── │                      │
│  仅 HTML/CSS/JS          │       JSON / Word 文件             │  持有 DeepSeek Key   │
└─────────────────────────┘                                   └──────────────────────┘
```

> ⚠️ 别人打开 GitHub Pages 时，如果他们本机没有运行后端，页面可以打开但无法进行 AI 分析和 Word 下载。

## 第一步：修改 CORS 配置

在 `backend/.env` 中，将 `CORS_ORIGINS` 替换为你的实际 GitHub Pages 地址：

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://你的GitHub用户名.github.io
```

## 第二步：修改 Vite base 路径

编辑 `frontend/vite.config.js`，将 `base` 改为你的 GitHub 仓库名：

```js
export default defineConfig({
  base: '/你的仓库名/',   // 例如 '/legal-ai-opinion/'
  // ...
})
```

## 第二步：构建前端

```bash
cd frontend
npm install
npm run build
```

构建产物在 `frontend/dist/` 目录。

## 第三步：部署到 GitHub Pages

### 方式一：使用 gh-pages 包

```bash
cd frontend
npm install -D gh-pages
```

在 `package.json` 中添加：

```json
{
  "scripts": {
    "deploy": "gh-pages -d dist"
  }
}
```

```bash
npm run deploy
```

### 方式二：GitHub Actions

在仓库中创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd frontend && npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./frontend/dist
```

### 方式三：手动部署

1. 在 GitHub 仓库 Settings → Pages 中，设置 Source 为 "GitHub Actions" 或直接选择分支。
2. 将 `frontend/dist` 内容推送到 `gh-pages` 分支。

## 第四步：使用

1. 在本机启动后端：`cd backend && uvicorn main:app --host 127.0.0.1 --port 8000`
2. 打开浏览器访问你的 GitHub Pages 地址。
3. 输入案件详情和期望目标，点击"开始深度分析"。

## 注意事项

1. 浏览器可能会因为 HTTPS (GitHub Pages) 请求 HTTP (127.0.0.1) 而触发 Mixed Content 警告。
   - Chrome：可能需要点击地址栏的盾牌图标允许不安全内容。
   - 或者使用 Firefox 进行测试。
2. 生产环境建议使用 HTTPS 后端，但本工具定位为个人本机使用，因此 HTTP 可接受。
3. 如需在移动设备上使用，可将后端部署到有公网 IP 的服务器并配置 HTTPS。
