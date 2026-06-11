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
| 1:10-1:25 | 筛选页配置弹窗：模式/难度/追问上限 → 开始面试 | InterviewConfig 细粒度自定义 |
| 1:25-1:40 | 面试页状态栏：模式、难度、阶段 | adaptive vs standardized |
| 1:40-1:55 | standardized 模式：连续 3 题题序固定 | 同岗公平比对叙事 |
| 1:55-2:05 | hr_friendly + 短答「嗯…」→ 鼓励话术 | 共情与评分隔离 |
| 2:05-2:15 | tech_lead 对比：水答「还行吧一般」→ Live 沟通分下降 | Evaluator + Calibrator |
| 2:15-2:25 | 换 hr_friendly 开场语气对比 | 双 persona |
| 2:25-2:40 | 报告页：过程 vs 终局 + 多维度 + 招聘决策 | 双轨评估创新点 |
| 2:40-2:50 | README「面试编排规则」专节 | 串联叙事 |

## 推荐样例

- `samples/job_description.txt`
- `samples/resume_good.txt`
- `samples/resume_poor.txt`

## 自检命令

```bash
python scripts/test_layer_a.py
python scripts/test_layer_b.py
python scripts/smoke_test.py
```
