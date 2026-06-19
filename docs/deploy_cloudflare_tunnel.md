# Cloudflare Tunnel 部署指南

通过 Cloudflare Tunnel 将本机后端暴露为公网 HTTPS 地址，配合 GitHub Pages 前端实现外网访问。

## 前提

- 本机已安装 [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
- 后端已在 `D:\2026GS\FL\legal-ai-opinion\backend` 配置完毕

### Windows 安装 cloudflared

**方式一：winget（推荐）**
```powershell
winget install -e --id Cloudflare.cloudflared
```
安装后**重新打开 PowerShell**，验证：
```powershell
cloudflared --version
```

**方式二：手动下载**
从 [Cloudflare 官方下载页面](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 下载 Windows 64-bit 版本（`cloudflared-windows-amd64.exe`），重命名为 `cloudflared.exe` 并放到 `C:\Windows\System32\` 或添加到 PATH。

### 如果 cloudflared 无法识别

1. **未安装**：按上述方式安装。
2. **PATH 未刷新**：关闭当前 PowerShell，重新打开。
3. **仍失败**：重启电脑，或手动将 `cloudflared.exe` 所在目录加入系统 PATH 环境变量。
4. **验证**：`Get-Command cloudflared` 应返回路径。

## 步骤

### 1. 启动本机后端

```powershell
cd D:\2026GS\FL\legal-ai-opinion\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 2. 启动 Cloudflare Tunnel

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

启动后会输出公网 HTTPS 地址，例如：

```
https://happy-meadow-lab.trycloudflare.com
```

### 3. 配置前端 API 地址

将公网地址填入前端环境变量：

```
VITE_API_BASE_URL=https://happy-meadow-lab.trycloudflare.com
```

**方式一：本地构建**

在 `frontend/.env.local` 中写入：

```dotenv
VITE_API_BASE_URL=https://happy-meadow-lab.trycloudflare.com
```

然后重新构建：

```powershell
cd D:\2026GS\FL\legal-ai-opinion\frontend
npm run build
```

**方式二：GitHub Actions 部署**

在 GitHub 仓库 Settings → Secrets and variables → Actions 中设置：

- Variable: `VITE_API_BASE_URL` = `https://happy-meadow-lab.trycloudflare.com`

> ⚠️ 不要在 GitHub Actions 中设置 `VITE_APP_ACCESS_TOKEN` Secret！令牌由用户在浏览器中手动输入。

推送代码后自动构建并部署到 GitHub Pages。

### 4. 用户输入访问令牌

1. 打开 GitHub Pages 地址（如 `https://你的用户名.github.io/legal-ai-opinion/`）
2. 点击右上角「未设置令牌」
3. 输入与后端 `APP_ACCESS_TOKEN` 一致的令牌
4. 点击「保存」，页面显示「后端 OK」即可正常使用

## 安全配置

### 架构原则

1. **后端真实令牌**仅保存在本机 `backend/.env`，不上传 GitHub。
2. **前端不内置令牌**：GitHub Pages 静态 JS 中不含任何 `APP_ACCESS_TOKEN`。
3. **用户手动输入**：打开页面后，在右上角「访问令牌」按钮中输入令牌。
4. **令牌仅存浏览器本地**：保存在 `localStorage`，不经过任何服务器。

### 访问令牌设置

**后端**（本机 `backend/.env`）：

```env
APP_ENV=production
APP_ACCESS_TOKEN=你的强随机令牌
```

> ⚠️ 生产模式下 `APP_ACCESS_TOKEN` 为空会导致后端拒绝启动。

生成强随机令牌：
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**前端**（用户在浏览器中操作）：

1. 打开 GitHub Pages 页面
2. 点击右上角「未设置令牌」按钮
3. 输入与后端一致的访问令牌
4. 点击「保存」

令牌保存到浏览器 `localStorage`，刷新页面后仍然有效。

### 公开路径（免 token）

以下路径无需令牌即可访问：
- `/api/health` — 健康检查
- `/api/model-status` — 模型状态
- `/api/config/runtime` — 运行时配置（已脱敏，不泄露 Key）

### 验证安全配置

```powershell
# ✅ 公开路径无需 token
curl https://xxxx.trycloudflare.com/api/health

# ❌ 分析请求需要 token（应返回 401）
curl -X POST https://xxxx.trycloudflare.com/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"case_detail":"test","goals":"test"}'

# ✅ 带正确 token 的分析请求
curl -X POST https://xxxx.trycloudflare.com/api/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secure-random-token-2026" \
  -d '{"case_detail":"test","goals":"test"}'
```

## 注意事项

- `trycloudflare.com` 地址在 cloudflared 进程关闭后会失效，重启后需更新地址。
- 每次重启 Tunnel 后，需更新 GitHub Actions Variable `VITE_API_BASE_URL` 并重新部署前端。
- 生产环境建议使用 Cloudflare Tunnel 的固定域名功能或自建反向代理。
- DeepSeek API Key 和 Tavily API Key 始终保持在本机 `backend/.env`，不会上传 GitHub。
- `backend/.env` 已加入 `.gitignore`，不会被提交到仓库。
- **令牌安全**：前端 GitHub Pages 静态 JS 不含令牌。令牌由用户在浏览器中输入，仅保存在本地 `localStorage`。
- 后端生产模式（`APP_ENV=production`）下，`APP_ACCESS_TOKEN` 为空会拒绝启动。
- 建议定期更换 `APP_ACCESS_TOKEN`，更换后通知用户重新输入。
