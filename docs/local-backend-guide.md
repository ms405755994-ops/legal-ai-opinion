# 本地后端运行指南

## 前置条件

- Python 3.10+
- 有效的 DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）

## 第一步：配置环境变量

```bash
cd backend

# 复制示例配置
copy .env.example .env
```

编辑 `.env`，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-reasoner
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://你的github用户名.github.io
OUTPUT_DIR=outputs
```

> ⚠️ **重要**：`DEEPSEEK_API_KEY` 只在 `backend/.env` 中配置，永远不会出现在前端代码或 GitHub Pages 上。

## 第二步：创建虚拟环境并安装依赖

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 第三步：启动后端

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功后，你会看到：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
```

## 验证

打开浏览器访问 [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)，应返回：

```json
{"status":"ok","version":"1.0.0","model":"deepseek-reasoner"}
```

## API 文档

启动后端后，可访问自动生成的 Swagger 文档：

- Swagger UI：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

## 数据源管理

数据源配置文件位于 `backend/data/sources.json`。

你也可以通过 API 或前端设置弹窗来管理数据源（增删改查）。

## 注意事项

1. **不要将 `.env` 提交到 Git**。`.gitignore` 已配置忽略该文件。
2. 后端仅监听 `127.0.0.1`，外部网络无法访问，保护 API Key 安全。
3. 第一版案例检索使用模拟数据，后续可接入真实数据源 API。
