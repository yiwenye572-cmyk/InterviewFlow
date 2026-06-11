# AI 招聘助手 MVP

智能招聘演示系统：**A 薄入口（简历解析 + 匹配筛选）+ B 深主线（LangGraph 模拟面试 Agent）**。

## 功能概览

1. **上传**：JD + 多份简历（PDF / DOCX / TXT）
2. **筛选（A 薄层）**：结构化抽取 → 语义相似度 + LLM  rubric 混合打分 → 是否推荐面试
3. **面试（B 深主线）**：可选面试官人设，多轮文字对话，SSE 流式输出，动态追问
4. **报告**：岗位匹配度、沟通能力、风险点、下轮建议；含 Self-reflection 修正

> A 层刻意不做批量静态试题生成——正式考察由 B 层 Agent 动态完成。

## 架构

```
static/ (HTML+CSS+JS)
    ↓ REST / SSE
FastAPI
    ├── DocumentParser → ResumeExtractor → MatchScorer → Chroma
    └── InterviewService → LangGraph nodes → Qwen (DashScope)
              ↓
         SQLite (会话/结构化数据)
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- 通义千问 DashScope API Key

### 2. 安装

```bash
cd AL
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

### 3. 启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开：http://localhost:8000

### 4. Demo 样本

`samples/` 目录提供了 JD 与两份对比简历（高匹配 / 低匹配）：

- `samples/job_description.txt`
- `samples/resume_good.txt`
- `samples/resume_poor.txt`

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs` | 上传 JD |
| POST | `/api/resumes?job_id=` | 批量上传简历 |
| POST | `/api/screen/{job_id}` | 触发筛选 |
| GET | `/api/screen/{job_id}/results` | 筛选结果 |
| POST | `/api/interview/start` | 开始面试 |
| GET | `/api/interview/{id}/stream` | SSE 流式输出 |
| POST | `/api/interview/{id}/message` | 提交回答 |
| POST | `/api/interview/{id}/end` | 结束并生成报告 |
| GET | `/api/interview/report/{id}` | 获取报告 |

## Prompt 设计思路

关键 Prompt 位于 `prompts/` 目录：

| 文件 | 用途 |
|------|------|
| `resume_extract.txt` | 结构化抽取，强调不臆造、模糊点写入 ambiguities |
| `match_score.txt` | JD-简历 rubric 打分 + recommend_interview |
| `persona_init.txt` | 基于 JD 生成面试官人设 |
| `ask_question.txt` | 动态提问，结合 ambiguities 与上轮评估 |
| `evaluate_answer.txt` | 静默评估：追问/跑题/简历矛盾检测 |
| `generate_report.txt` | 结构化评估报告 |
| `report_reflection.txt` | 报告 Self-reflection，修正矛盾 |

结构化输出统一走 `structured_completion()`：Pydantic 校验 → 失败重试 → JSON repair。

## 难点与解决方案

### 1. 多轮面试 Context 爆炸
- 完整对话存 SQLite；每 3 轮 LLM 压缩为 `running_summary`
- System prompt 始终锚定 JD 摘要 + 结构化简历 + ambiguities

### 2. LLM JSON 不稳定
- DashScope `response_format: json_object` + Pydantic 校验
- 失败后追加纠错 prompt 重试（最多 2 次）

### 3. 流式 SSE 与同步 LLM
- 后台线程生产 token，async 生成器通过 Queue 转发给 SSE
- 前端 `EventSource` 消费，打字机效果

### 4. 混合匹配分
- 语义分（Chroma cosine × 40%）+ LLM rubric 分（× 60%）
- 双阈值：`final_score >= 60` 且 `recommend_interview=true` 才可进入面试

## Demo 视频脚本（≥2 分钟）

1. 上传 `job_description.txt` + `resume_good.txt` + `resume_poor.txt`
2. 展示筛选列表：高分 vs 低分及理由对比
3. 对高分候选人选择「严厉的技术总监」开始面试
4. 回答 2~3 轮，展示针对简历模糊点的追问
5. 结束面试，展示完整评估报告

## 技术栈

- **后端**：FastAPI, SQLAlchemy, LangGraph, DashScope (Qwen)
- **向量**：Chroma（本地持久化）
- **前端**：原生 HTML / CSS / JavaScript
- **文档解析**：PyMuPDF, python-docx

## 项目结构

```
app/
  main.py           # FastAPI 入口
  api/              # REST + SSE 路由
  services/         # 业务逻辑
    interview/      # LangGraph 面试 Agent
static/             # 前端静态页
prompts/            # Prompt 模板
samples/            # Demo 样例文件
data/               # SQLite + Chroma（运行时生成，已 gitignore）
```

## License

MIT — 仅供笔试 Demo 使用
