# AI 招聘助手 MVP

> **在线演示**：https://nainong.tech/airecruit/

智能招聘演示系统，**场景 A（简历解析与筛选）+ 场景 B（LangGraph 模拟面试 Agent）端到端串联**，覆盖从非结构化输入到结构化招聘决策的完整闭环。

---

## 交付物清单

| 交付项 | 位置 / 说明 |
|--------|-------------|
| **在线演示** | **https://nainong.tech/airecruit/** |
| **可运行源代码** | 克隆后 `pip install -r requirements.txt` + 配置 `.env` 即可启动 |
| **环境配置与启动** | [快速开始](#快速开始) |
| **架构与数据流** | [系统架构](#系统架构) |
| **Prompt 设计思路** | [Prompt 设计](#prompt-设计思路) |
| **难点与解决方案** | [难点与解决方案](#难点与解决方案) |
| **AI 工程化能力** | [LLM Harness](#llm-harness) · [简历 Grounding](#简历-grounding-回验) · [Stream Guard](#流式输出后验stream-guard) |
| **LLM Harness 单测** | `python scripts/test_llm_harness.py`（11 项 mock） |
| **简历 Grounding 单测** | `python scripts/test_resume_validator.py`（6 项规则） |
| **Stream Guard 单测** | `python scripts/test_stream_guard.py`（7 项 mock） |
| **界面截图** | [`screenshots/`](screenshots/) 主流程配图，见 [界面预览](#界面预览) |

---

## 功能概览

1. **上传**：左侧历史岗位复用 JD，右侧上传/勾选简历 → **上传并筛选**（支持 PDF / DOCX / TXT）
2. **筛选（A 层）**：结构化抽取 → **Grounding 回验** → 混合打分 → 追问包（3–5）→ 试题包（≥10，懒加载）→ 决策建议
3. **面试（B 层）**：消费 A 层种子，LangGraph 多轮动态面试（自适应 / 标准化双模式）
4. **报告**：岗位匹配、沟通能力、风险点、下轮建议；Self-reflection 修正；**异步生成 + 进度轮询**

> **A 层与 B 层分工**：A 输出结构化决策与预生成考察提纲；B 负责动态追问与终评。未推荐候选人也可进入模拟面试。

> **TXT 说明**：`.txt` 与 PDF/DOCX 同等支持。筛选页 `failed` 多为 LLM 结构化抽取失败，可运行 `python scripts/diagnose_resume.py --file JL.txt` 本地复现。

### 前端交互（Demo 易用性）

- **流程步骤条**：上传 → 筛选 → 面试 → 报告（圆圈 + 连接线，当前步高亮，已完成可回跳）
- **宽屏布局**：主流程页适配大屏，减少两侧留白
- **全站导航**：顶栏「首页 / 完整历史」+ 步骤条与操作按钮分区
- **报告页**：招聘决策高亮、多维度卡片、评分时间线、过程 vs 终局对比（**中文展示**）
- **配色**：企业商务风（主色 `#4080FF`，状态色绿/橙/红）

### 界面预览

按主流程顺序（上传 → 筛选 → 面试 → 报告 → 历史回看）：

| 步骤 | 说明 |
|------|------|
| 1 上传 | 左侧历史 JD，右侧上传/勾选简历并筛选 |
| 2 筛选 | 综合分、维度条、追问与模拟面试入口 |
| 3 面试 | 开场状态栏 + 右侧实时评估 / 面试议程 |
| 4 报告 | 招聘决策、多维度分、评分时间线 |
| 5 历史 | 岗位与面试记录持久化列表 |

**1. 上传（首页）**

![上传界面](screenshots/上传界面.png)

**2. 筛选结果**

![筛选界面](screenshots/筛选界面.png)

**3. 模拟面试 — 初始**

![面试初始界面](screenshots/面试初始界面.png)

**4. 模拟面试 — 进行中**

![面试中界面](screenshots/面试中界面.png)

**5. 评估报告**

![报告界面](screenshots/报告界面.png)

**6. 历史岗位 / 会话回看**

![历史会话界面](screenshots/历史会话界面.png)

---

## 场景 A：智能简历解析与筛选

### 与题目映射

| 题目要求 | 实现 |
|----------|------|
| 结构化提取 + 向量/结构化存储 | `ResumeStructured` / `JDStructured` → SQLite；摘要 embedding → Chroma |
| 智能匹配 0–100 + 理由 + 是否推进 | 40% 语义 + 60% LLM rubric；`dimension_scores` + `decision_summary` |
| 试题生成 ≥10 道 | `QuestionPack` 懒加载 API + 筛选页抽屉 |
| 追问模拟 3–5 道 | `FollowupPack` 筛选时同步生成 + 详情展开 |

### 五阶段流水线

```
上传解析 → 结构化抽取 → [Grounding 回验] → 向量索引 → 混合打分 → 追问包 / 试题包
```

### A → B 交接

面试启动时，`InterviewService` 将 gaps、FollowupPack、QuestionPack 考察点注入 Agent，优先覆盖 A 层识别的模糊点与能力差距。

---

## 场景 B：AI 模拟面试官 Agent

### 与题目映射

| 题目要求 | 实现 |
|----------|------|
| 角色设定（技术总监 / HR） | `PersonaProfile` + LLM 化开场；`tech_lead` / `hr_friendly` 全链路一致 |
| 多轮对话 + 记忆 + 动态追问 | LangGraph `Evaluate → Route → FollowUp/Plan/Ask/Closing`；SQLite 消息 + `running_summary` |
| 非机械问答 | `TopicPlanner` 阶段规划 + competencies 覆盖追踪 |
| 实时评估报告 | LiveAssessment + **Evaluator/Calibrator 双 Agent** + 终局 Report + Self-reflection |

### 双轨评估（Evaluator + Calibrator）

```mermaid
flowchart LR
  answer[CandidateAnswer] --> evalAgent[EvaluateAgent]
  evalAgent --> calAgent[ScoreReviewAgent]
  calAgent --> live[LiveAssessment]
  calAgent --> log[evaluations_log]
  log --> report[FinalReport]
  live --> report
```

- **EvaluateAgent**：静默评估回答质量、沟通信号、证据密度
- **ScoreReviewAgent**：招聘方视角校准分数，纠正「水答高分」
- **LiveAssessment**：过程分（加权 + 规则封顶）
- **FinalReport**：多维度 + 过程 vs 终局对比 + 招聘决策 rationale（简体中文）

### LangGraph 状态图

```
InitPersona → StreamOpening → WaitAnswer
  → EvaluateAnswer → ScoreReview → RouteDecision
    → StreamEncouragement | FollowUpQuestion | PlanNextTopic → AskQuestion | StreamClosing → GenerateReport
```

**双面试模式**（`InterviewConfig.interview_mode`）：

| 模式 | 适用场景 | 行为 |
|------|----------|------|
| `adaptive`（默认） | 深度评估、个性化追问 | TopicPlanner + A 层种子 + 动态追问 |
| `standardized` | 同岗公平比对 | 固定 QuestionPack 题序 + 每题固定 N 次追问 |

筛选页弹窗与 `POST /api/interview/start` 均支持完整 `InterviewConfig`（模式、人设、难度、严厉度/亲和度、追问上限、鼓励话术等）。

### 面试编排要点

- **追问上限**：`max_followup_streak`（0–3，默认 2），达上限后换题并标记 `at_risk`
- **鼓励话术**：`hesitant` / `stuck` 时可输出鼓励，**Calibrator 不参与**，不抬高分数
- **输入安全**：`input_guard.py` 拦截 jailbreak / prompt 泄露，短路 Evaluate
- **输出后验**：`stream_guard.py` 对开场 / 追问 / 提问缓冲校验，失败则 rewrite 或模板兜底（见 [Stream Guard](#流式输出后验stream-guard)）
- **评分可审计**：`evaluations_log` + 报告页「评分时间线」展示每轮 Δ 与依据
- **语音 MVP（可选）**：豆包 ASR + TTS，`/voice/turn` 一轮语音；未配置 Key 时返回 503，文字模式不受影响

### 双向反馈飞轮

- **招聘方**：终局报告 gaps → `ResumeStructured.interview_feedback`
- **候选人**：报告页 1–5 星 + 简述 → 同岗位下次面试注入 persona（**不影响评分**）

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  static/  首页 · 筛选 · 面试 · 报告 · 历史 · 岗位详情        │
│           HTML + CSS + JS（流程步骤条 / SSE / 轮询）          │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST / SSE
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI (app/main.py)                                      │
│  ├── jobs / resumes / screening   ← 场景 A                  │
│  └── interview (LangGraph + voice) ← 场景 B                  │
└──────────┬───────────────────────────────┬──────────────────┘
           │                               │
    DocumentParser                    InterviewService
    ResumeExtractor                   LangGraph nodes
    MatchScorer + Chroma              Qwen (DashScope)
           │                               │
           └───────────┬───────────────────┘
                       ▼
              SQLite (结构化 + 会话 + 报告)
              Chroma (简历/JD 向量)
```

---

## 快速开始

### 1. 环境要求

- Python 3.11+
- 通义千问 DashScope API Key（必需）
- 火山引擎豆包语音 `VOLC_SPEECH_API_KEY`（可选，语音面试）

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
# 方式一（推荐，Windows 双击或命令行）
start.bat          # 内部调用 start.ps1，自动创建 venv 并安装依赖

# 方式二
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开：**http://localhost:8000**


### 4. 主流程操作

1. 首页左侧选/建 JD → 右侧上传简历 → **上传并筛选**（默认异步并发，弹窗显示进度）→ 见 [上传界面](screenshots/上传界面.png)
2. **查看筛选结果** → 展开详情 / 生成试题 / **模拟面试** → 见 [筛选界面](screenshots/筛选界面.png)
3. 面试页对话（可切换文字/语音）→ **结束面试并生成报告**（默认异步，报告页轮询进度）→ 见 [面试初始](screenshots/面试初始界面.png) / [面试中](screenshots/面试中界面.png)
4. 报告页查看决策与评分时间线 → **继续面试下一位** 或 **完整历史** 回看 → 见 [报告界面](screenshots/报告界面.png) / [历史会话界面](screenshots/历史会话界面.png)

完整配图见 [界面预览](#界面预览)。

### 5. Demo 样例

| 文件 | 说明 |
|------|------|
| `samples/job_description.txt` | 示例 JD |
| `samples/resume_good.txt` | 高匹配简历 |
| `samples/resume_poor.txt` | 低匹配简历 |
| `samples/shopee_jd.txt` + `samples/yeyiwen_resume.txt` | Markdown 模板回归 |
| 项目根目录 `JD.txt` / `JL.txt` | 各含 **2 组虚构 Mock**（`====` 分隔）；**上传 Demo 时请只复制其中一组** 另存为单独 `.txt`，避免整文件含两套 JD/简历 |

---

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs` | 上传 JD |
| GET | `/api/jobs` | 历史岗位列表 |
| DELETE | `/api/jobs/{id}` | 删除岗位及关联数据 |
| GET | `/api/jobs/{id}/overview` | JD 摘要 + 面试记录 |
| POST | `/api/resumes?job_id=` | 批量上传简历 |
| GET | `/api/jobs/{id}/resumes` | 岗位下简历列表 |
| POST | `/api/screen/{job_id}` | 筛选；`async: true` 异步批次（默认） |
| GET | `/api/screen/batch/{batch_id}` | 异步筛选进度 |
| GET | `/api/screen/{job_id}/results` | 筛选结果 |
| GET | `/api/screen/{job_id}/detail/{resume_id}` | 单候选人 A 层详情 |
| GET | `/api/screen/{job_id}/questions/{resume_id}` | 懒加载试题包（≥10） |
| POST | `/api/interview/start` | 开始面试 |
| GET | `/api/interview/{id}/stream` | SSE 流式输出 |
| POST | `/api/interview/{id}/message` | 提交回答 |
| POST | `/api/interview/{id}/voice/turn` | 语音一轮（可选） |
| GET | `/api/interview/{id}/live` | 实时评估快照 |
| GET | `/api/interview/{id}/status` | 面试状态 / 议程 |
| GET | `/api/interview/{id}/messages` | 历史消息 |
| POST | `/api/interview/{id}/end` | 结束面试；默认 **202 异步** 生成报告 |
| GET | `/api/interview/report/{id}/status` | 报告生成进度 |
| GET | `/api/interview/report/{id}` | 获取报告（含 `score_timeline`） |
| POST | `/api/interview/{id}/feedback` | 候选人体验反馈 |

完整 REST 映射见上文 B 层章节；岗位模板 `templates/tech_backend.json`、打分细则 `POST /api/jobs/{id}/rubric` 等见 [演进能力](#演进能力)。

---

## Prompt 设计思路

关键 Prompt 位于 `prompts/` 目录，结构化输出统一走 [`app/services/llm/`](app/services/llm/) Harness 的 `structured_completion()`：Pydantic 校验 → 按错误类型智能 Retry → JSON repair。

| 文件 | 用途 |
|------|------|
| `resume_extract.txt` | 结构化抽取，不臆造，模糊点写入 ambiguities |
| `jd_extract.txt` | JD 结构化：必备技能、年限、硬性条件 |
| `match_score.txt` | 维度 rubric 打分 + decision_summary |
| `followup_probe.txt` | 3–5 道简历追问 |
| `question_generate.txt` | ≥10 道预生成面试题 |
| `persona_init.txt` / `opening_message.txt` | 人设与风格化开场 |
| `evaluate_answer.txt` / `score_review.txt` | Evaluate + Calibrator 双 Agent |
| `followup_question.txt` / `topic_planner.txt` / `ask_question.txt` | 动态追问与换题 |
| `generate_report.txt` / `report_reflection.txt` | 终局报告 + Self-reflection（**简体中文**） |

---

## 难点与解决方案

| 挑战 | 方案 |
|------|------|
| 多轮 Context 爆炸 | SQLite 存全量对话；每 3 轮 LLM 压缩 `running_summary` |
| LLM JSON 不稳定 | `response_format: json_object` + Pydantic + 纠错重试（最多 2 次） |
| 流式 SSE 与同步 LLM | 后台线程 + Queue 转发 token |
| 混合匹配分 | Chroma 语义 40% + LLM rubric 60%；双阈值推荐 |
| 「水答高分」 | Calibrator 独立校准；时间线可审计 |
| Prompt 注入 / 越狱 | `input_guard` 规则预检（候选人输入）+ Prompt 加固 |
| 简历结构化幻觉 | `resume_validator` 抽取后 grounding；`validation_*` 写入 `score_flags` |
| 面试官输出跑题 / 泄露 | `stream_guard` 缓冲后验 + LLM rewrite + 模板兜底 |
| LLM 调用不可观测 | `app/services/llm/` 统一 Harness + `data/llm_calls.jsonl` |
| 报告生成耗时 | 异步 Worker + 阶段进度；前端轮询 skeleton |
| 语音集成 | 豆包 ASR WebSocket + TTS SSE；文本模式默认不受影响 |

---

## AI 工程化能力

面向阿里题目「Agent 编排 + Harness + 幻觉/格式治理」，本项目在 A/B 两层分别落地三层防护：

| 层级 | 模块 | 作用 |
|------|------|------|
| 全链路 | [`app/services/llm/`](app/services/llm/) | 统一 LLM 调用、Timeout、日志、智能 Retry |
| A 层筛选 | [`app/services/resume_validator.py`](app/services/resume_validator.py) | 简历抽取**成功后**事实回验 |
| B 层面试 | [`app/services/interview/stream_guard.py`](app/services/interview/stream_guard.py) | 开场 / 追问 / 提问**流式输出**后验 |
| B 层面试 | [`app/services/interview/input_guard.py`](app/services/interview/input_guard.py) | **候选人**输入安全（与 Stream Guard 分工） |

---

## LLM Harness

所有 DashScope 文本调用统一经 `app/services/llm/`（[`chat_completion`](app/services/llm/__init__.py) / `chat_completion_stream` / `structured_completion` 对外签名不变，11 个业务调用方无需改 import）。

### 能力

| 能力 | 说明 |
|------|------|
| **Timeout** | 普通 structured 30s、报告 60s、流式 idle 120s（`.env` 可配） |
| **截断** | system / user 分层字符上限；JSONL 记录 `truncated` 标记 |
| **JSONL 日志** | `data/llm_calls.jsonl`：`call_id`、model、latency、tokens、cost_cny、retry_attempt |
| **智能 Retry** | JSON 解析 / Pydantic 校验 / API / Timeout 分类；校验失败可升级 `qwen-turbo → qwen-plus` |
| **观测扩展** | `TraceAdapter` 预留 LangSmith / OpenTelemetry（默认 NoOp） |

### 环境变量

```env
LLM_LOG_ENABLED=true
LLM_LOG_PATH=data/llm_calls.jsonl
LLM_TIMEOUT_DEFAULT=30
LLM_TIMEOUT_REPORT=60
LLM_TIMEOUT_STREAM=120
LLM_MAX_SYSTEM_CHARS=8000
LLM_MAX_USER_CHARS=12000
LLM_STRUCTURED_MAX_RETRIES=2
LLM_TRACE_BACKEND=none
```

### 自测

```bash
python scripts/test_llm_harness.py   # mock 单测，不耗 API Key
```

---

## 简历 Grounding 回验

LLM 结构化抽取**成功后**（**非** `parse_partial_fallback` 降级路径），[`app/services/resume_validator.py`](app/services/resume_validator.py) 在 [`match_scorer.py`](app/services/match_scorer.py) 入库打分前对原文做事实回验：

```
extract_resume_structured → validate_resume_grounding → structured_json + 打分
build_partial_structured（抽取失败降级）→ 跳过回验
```

### 校验项

| 类型 | 规则 | 典型 flag |
|------|------|-----------|
| 字段 grounding | 姓名、公司、学校、联系方式须在原文 fuzzy 命中 | `validation_name_ungrounded`、`validation_company_ungrounded:*` |
| Skills | 每个 skill 子串 / token 匹配；未命中写入 `ambiguities` | `validation_skill_ungrounded:*`、`validation_skills_low_ratio` |
| 年限 sanity | `years_experience` 与经历时间段估算矛盾 | `validation_years_inflated` |

### 处置策略

- `validation_*` flags 并入筛选结果 **`score_flags`**（API 可见）
- 严重幻觉：`success → partial`（`validation_force_partial`）
- warn/fail 时从 **`final_score` 扣** `RESUME_VALIDATION_SCORE_PENALTY` 分（默认 5）

### 环境变量

```env
RESUME_VALIDATION_ENABLED=true
RESUME_VALIDATION_SKILL_MIN_RATIO=0.6
RESUME_VALIDATION_NAME_REQUIRED=true
RESUME_VALIDATION_SCORE_PENALTY=5
RESUME_VALIDATION_FORCE_PARTIAL_SEVERE=2
```

### 自测

```bash
python scripts/test_resume_validator.py   # 纯规则单测，不耗 API
```

---

## 流式输出后验（Stream Guard）

B 层 **开场 / 追问 / 提问** 在 SSE 下发前经 [`app/services/interview/stream_guard.py`](app/services/interview/stream_guard.py) **缓冲完整文本 → 后验 → 再分块 yield**（避免坏内容已推送无法撤回）。`stream_encouragement` / `stream_closing` 不在此范围。

```mermaid
flowchart LR
  stream[LLM stream_opening/followup/question] --> buf[缓冲全文]
  buf --> validate[validate_stream_output]
  validate -->|pass| yield[SSE 分块 yield]
  validate -->|fail| rewrite[LLM rewrite 1 次]
  rewrite -->|pass| yield
  rewrite -->|fail| tpl[persona 模板兜底]
  tpl --> yield
```

```
stream_opening/followup/question → 缓冲全文 → validate → [LLM rewrite] → [模板兜底] → SSE 分块
```

### 规则后验

| 检查 | flag 示例 |
|------|-----------|
| 过短 / 空 | `stream_guard_too_short`、`stream_guard_empty` |
| AI 自述 | `stream_guard_ai_leak` |
| System 泄露 | `stream_guard_system_leak`（复用 input_guard 模式） |
| 离题指令 | `stream_guard_off_topic` |
| 无提问（开场/换题） | `stream_guard_no_question` |
| 人设漂移 | `stream_guard_persona_drift`（tech_lead 忌 HR 腔；hr_friendly 忌攻击性用语） |

### 失败策略

1. 规则 fail 或仅 persona 漂移 → 可选 **fast 模型重写 1 次**（`purpose=stream_guard_rewrite`）
2. 仍 fail → **persona 模板兜底**（`stream_guard_template_fallback`）

### 与 input_guard 分工

| 模块 | 校验对象 |
|------|----------|
| `input_guard` | **候选人**回答（jailbreak / 泄露 / 离题） |
| `stream_guard` | **面试官**流式输出（AI 泄露 / 人设漂移 / 无提问） |

### 环境变量

```env
STREAM_GUARD_ENABLED=true
STREAM_GUARD_MIN_CHARS=10
STREAM_GUARD_MAX_CHARS=2000
STREAM_GUARD_LLM_REWRITE=true
```

关闭后验：`STREAM_GUARD_ENABLED=false`，行为与改造前一致（边收边 yield）。

### 自测

```bash
python scripts/test_stream_guard.py   # mock 单测，不耗 API
```

---

## Docker 部署

本地验证与服务器部署均使用项目根目录的 `docker-compose.yml`。容器内 uvicorn 监听 `8000`，宿主机映射为 **`127.0.0.1:8001`**（避开 MAEC-SYS 占用的 8000）。详见 [`服务器环境.md`](服务器环境.md) 端口说明。

### 本地验证

```bash
cp .env.example .env
# 编辑 .env，填入有效的 DASHSCOPE_API_KEY

docker compose up -d --build
curl http://127.0.0.1:8001/health
# 期望: {"status":"ok"}
```

本地开发可不设置 `PUBLIC_BASE_PATH`，直接访问 `http://127.0.0.1:8001/`。

### 服务器（nainong.tech）

1. 同步代码到 `/var/www/airecruit`
2. 配置 `.env`（`chmod 600`），必须设置：
   - `DASHSCOPE_API_KEY`
   - `PUBLIC_BASE_PATH=/airecruit`
   - `DATABASE_URL=sqlite:////app/data/app.db`
   - `CHROMA_PATH=/app/data/chroma`
3. `mkdir -p data && docker compose up -d --build`
4. 在 Nginx **80 与 443** 两个 `server {}` 块内追加（不修改现有 location）：

```nginx
    location /airecruit/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
```

5. `sudo nginx -t && sudo systemctl reload nginx`
6. 验证：`curl -s https://nainong.tech/airecruit/health`

**对外访问地址**：`https://nainong.tech/airecruit/`

**数据备份**：`tar czf data-backup.tar.gz data/`

> **注意**：筛选批次与报告生成有进程内状态，请保持 **单容器、单 worker**（Dockerfile 已配置 `--workers 1`），不要水平扩容多副本。

---

## 测试与自检

```bash
# AI 工程化单测（mock，不耗 API Key）
python scripts/test_llm_harness.py
python scripts/test_resume_validator.py
python scripts/test_stream_guard.py

# 环境检查
python scripts/check_env.py

# 一键审计矩阵（推荐提交前跑通）
python scripts/run_audit_suite.py

# 分层测试
python scripts/test_layer_a.py      # 场景 A
python scripts/test_layer_b.py      # 场景 B
python scripts/test_p0.py
python scripts/test_screen_batch.py # 异步筛选
python scripts/test_report_async.py # 异步报告
python scripts/test_candidate_feedback.py
python scripts/smoke_test.py

# UI 静态检查（不启动浏览器）
python scripts/verify_ui_static.py

# 简历解析诊断
python scripts/diagnose_resume.py --file JL.txt
```

---

## 演进能力

- 岗位模板：`templates/tech_backend.json`、`product_manager.json`
- 公司打分细则：`POST /api/jobs/{id}/rubric`
- 测评摘要：`POST /api/resumes/{id}/assessment-notes`
- 历史持久化：`history.html` → `job.html` → `report.html`

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI, SQLAlchemy, **LangGraph**, DashScope (Qwen) |
| 向量 | Chroma（本地持久化） |
| 存储 | SQLite（`data/app.db`） |
| 前端 | 原生 HTML / CSS / JavaScript（无框架） |
| 文档解析 | PyMuPDF, python-docx |
| 语音（可选） | 火山引擎 openspeech ASR/TTS |

---

## 项目结构

```
app/
  main.py              # FastAPI 入口
  api/                 # REST + SSE 路由
  services/
    llm/                 # LLM Harness（client / retry / log_store）
    resume_validator.py  # A 层抽取后 grounding
    interview/           # LangGraph 面试 Agent
      stream_guard.py    # B 层流式输出后验
      input_guard.py     # 候选人输入安全
    voice/               # 豆包 ASR/TTS 客户端
    screen_batch.py      # 异步筛选批次
    report_async.py      # 异步报告生成
static/
  index.html           # 上传 + 筛选入口
  screening.html       # 筛选结果
  interview.html       # 模拟面试
  report.html          # 评估报告
  history.html / job.html
  css/                 # style.css, app-ui.css, interview.css, report.css
  js/                  # api.js, nav.js, home.js, …
prompts/               # Prompt 模板
templates/             # 岗位 rubric 模板
samples/               # Demo 样例
screenshots/           # README 界面配图
scripts/               # 测试与诊断脚本
  test_llm_harness.py      # Plan 1：LLM Harness
  test_resume_validator.py # Plan 2：简历 Grounding
  test_stream_guard.py     # Plan 3：Stream Guard
data/                  # SQLite + Chroma + llm_calls.jsonl（运行时，已 gitignore）

