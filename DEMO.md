# Demo 录制脚本（≥2 分钟）

## 准备

1. 配置 `.env` 中的 `DASHSCOPE_API_KEY`
2. 启动服务：`uvicorn app.main:app --reload --port 8000`
3. 打开 http://localhost:8000

## 分镜

| 时间 | 画面 | 旁白要点 |
|------|------|----------|
| 0:00-0:15 | 首页上传 JD + 2 份简历 | A 层：非结构化 → 结构化决策 |
| 0:15-0:40 | 筛选结果：分数、维度条、decision_summary | 混合打分 40% 语义 + 60% LLM |
| 0:40-0:55 | 展开详情：追问 3–5 条 | 题目要求的追问模拟 |
| 0:55-1:10 | 点击「生成试题」抽屉 ≥10 题 | 题目要求的试题生成 |
| 1:10-1:25 | 选择 tech_lead persona，观察 **LLM 风格化开场** | 非硬编码模板 |
| 1:25-1:45 | 故意 vague 回答 → Agent **同话题追问**；侧栏 Live 分数变化 | 动态追问路由 |
| 1:45-1:55 | 展示 phase / 考察点覆盖 / status API | TopicPlanner + A 层种子 |
| 1:55-2:10 | 结束 → 报告含过程摘要 + 风险点 | Live + Final 双轨评估 |
| 2:10-2:20 | README A 层架构图 | 串联叙事 |

## 推荐样例

- `samples/job_description.txt`
- `samples/resume_good.txt`
- `samples/resume_poor.txt`
