# Demo 录制脚本（≥2 分钟）

## 准备

1. 配置 `.env` 中的 `DASHSCOPE_API_KEY`
2. 启动服务：`uvicorn app.main:app --reload --port 8000`
3. 打开 http://localhost:8000

## 分镜

| 时间 | 画面 | 旁白要点 |
|------|------|----------|
| 0:00-0:20 | 首页上传 JD + 两份简历 | 介绍系统：A 层筛选 + B 层 Agent 面试 |
| 0:20-0:50 | 筛选结果页 | 对比高分/低分、语义分与 LLM 分、推荐理由 |
| 0:50-1:40 | 选「技术总监」开始面试，回答 2~3 轮 | 展示 SSE 流式输出与针对简历模糊点的追问 |
| 1:40-2:10 | 评估报告页 | 岗位匹配、沟通能力、风险点、下轮建议 |
| 2:10-2:20 | README 架构图 / 项目结构 | 技术栈：FastAPI + LangGraph + Qwen + Chroma |

## 推荐样例文件

- `samples/job_description.txt`
- `samples/resume_good.txt`（高匹配）
- `samples/resume_poor.txt`（低匹配）

## 面试回答示例（可提前准备）

1. **自我介绍**：结合 FastAPI + LangGraph 项目经历
2. **技术深挖**：描述简历中 AI 招聘助手的架构与混合匹配策略
3. **模糊点追问**：若被问到「开源贡献 LangChain 文档」— 可诚实说明参与程度
