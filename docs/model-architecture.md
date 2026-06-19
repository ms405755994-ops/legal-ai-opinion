# 模型架构说明

## 当前模型分工

- **DeepSeek**：主分析模型，负责案件拆解、关键词生成、报告生成
- **Lawformer**：类案相似度排序（V1 mock）
- **DISC-LawLLM**：法律复核（V1 mock）
- **InternLM-Law**：备用法律复核（V1 mock）

## 架构图

```
用户输入 → DeepSeek 案件拆解 → 关键词生成 → 在线检索 → 链接筛选 → 报告生成 → Word 导出
```
