import { showToast, apiRequest, getQueryParam, scoreClass } from "/static/js/api.js";

const jobId = getQueryParam("job_id");
let pendingResumeId = null;

const modal = document.getElementById("persona-modal");
const questionDrawer = document.getElementById("question-drawer");
modal.style.display = "none";
questionDrawer.style.display = "none";

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function dimensionBar(label, score) {
  const val = Number(score) || 0;
  return `
    <div class="dim-row">
      <span class="dim-label">${escapeHtml(label)}</span>
      <div class="dim-track"><div class="dim-fill" style="width:${val}%"></div></div>
      <span class="dim-val">${val}</span>
    </div>`;
}

function renderDimensionScores(scores) {
  const labels = {
    skill_fit: "技能",
    experience_fit: "经验",
    domain_fit: "领域",
  };
  const keys = Object.keys(labels);
  if (!scores || !keys.some((k) => scores[k] != null)) return "";
  return `<div class="dim-bars">${keys
    .map((k) => dimensionBar(labels[k], scores[k] ?? 0))
    .join("")}</div>`;
}

function renderFollowups(followups) {
  if (!followups?.length) return "<p class='muted'>暂无追问建议</p>";
  return `<ol class="followup-list">${followups
    .map(
      (f) => `<li>
        <strong>${escapeHtml(f.question)}</strong>
        <div class="muted small">针对：${escapeHtml(f.target_ambiguity)} · ${escapeHtml(f.probe_intent)} · ${escapeHtml(f.difficulty)}</div>
      </li>`
    )
    .join("")}</ol>`;
}

async function loadResults() {
  if (!jobId) {
    showToast("缺少 job_id 参数", true);
    return;
  }

  const container = document.getElementById("results-container");
  try {
    const data = await apiRequest(`/api/screen/${jobId}/results`);
    if (!data.results.length) {
      container.innerHTML = "<p>暂无简历，请先上传。</p>";
      return;
    }

    const rows = data.results
      .map((r, idx) => {
        const badge = r.recommend_interview
          ? '<span class="badge badge-success">推荐面试</span>'
          : '<span class="badge badge-muted">暂不推荐</span>';
        const reasons = r.reasons.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
        const gaps = r.gaps?.length
          ? `<ul class="gap-list">${r.gaps.map((g) => `<li>${escapeHtml(g)}</li>`).join("")}</ul>`
          : "";
        const btnClass = r.recommend_interview ? "btn-primary" : "btn-secondary";
        const skills = (r.skills || [])
          .slice(0, 8)
          .map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`)
          .join("");
        const decision = r.decision_summary
          ? `<p class="decision-summary">${escapeHtml(r.decision_summary)}</p>`
          : "";

        return `
        <tr class="result-row" data-idx="${idx}">
          <td>
            <strong>${escapeHtml(r.candidate_name)}</strong><br/>
            <small class="muted">${escapeHtml(r.filename)}</small>
            ${r.parse_status !== "success" ? `<br/><span class="badge badge-warning">${escapeHtml(r.parse_status)}</span>` : ""}
          </td>
          <td><span class="score ${scoreClass(r.final_score)}">${r.final_score}</span></td>
          <td>${r.semantic_score.toFixed(1)} / ${r.llm_score.toFixed(1)}</td>
          <td>
            ${badge}
            ${decision}
            ${renderDimensionScores(r.dimension_scores)}
            <ul class="reason-list">${reasons}</ul>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm toggle-detail" data-idx="${idx}">详情</button>
            <button class="btn ${btnClass} btn-sm start-interview" data-resume-id="${r.resume_id}">模拟面试</button>
            <button class="btn btn-secondary btn-sm load-questions" data-resume-id="${r.resume_id}">${r.has_question_pack ? "查看试题" : "生成试题"}</button>
          </td>
        </tr>
        <tr class="detail-row hidden" id="detail-${idx}">
          <td colspan="5">
            <div class="detail-panel">
              <p><strong>摘要：</strong>${escapeHtml(r.summary || "—")}</p>
              <div class="skill-tags">${skills}</div>
              <h4>能力差距</h4>
              ${gaps || "<p class='muted'>无</p>"}
              <h4>简历追问建议（3–5 道）</h4>
              ${renderFollowups(r.followups)}
            </div>
          </td>
        </tr>`;
      })
      .join("");

    container.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>候选人</th>
            <th>综合分</th>
            <th>语义/LLM</th>
            <th>评估</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;

    document.querySelectorAll(".toggle-detail").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = document.getElementById(`detail-${btn.dataset.idx}`);
        row.classList.toggle("hidden");
      });
    });

    document.querySelectorAll(".start-interview").forEach((btn) => {
      btn.addEventListener("click", () => {
        pendingResumeId = btn.dataset.resumeId;
        document.getElementById("mode-select").value = "adaptive";
        document.getElementById("persona-select").value = "tech_lead";
        document.getElementById("role-title").value = "";
        document.getElementById("difficulty-select").value = "medium";
        document.getElementById("strictness-range").value = "3";
        document.getElementById("strictness-val").textContent = "3";
        document.getElementById("warmth-range").value = "3";
        document.getElementById("warmth-val").textContent = "3";
        document.getElementById("followup-max").value = "2";
        document.getElementById("enable-encouragement").checked = false;
        modal.style.display = "flex";
      });
    });

    document.querySelectorAll(".load-questions").forEach((btn) => {
      btn.addEventListener("click", () => loadQuestions(btn.dataset.resumeId));
    });
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger)">${escapeHtml(err.message)}</p>`;
  }
}

async function loadQuestions(resumeId) {
  const body = document.getElementById("question-drawer-body");
  body.innerHTML = "<p>生成中，请稍候...</p>";
  questionDrawer.style.display = "flex";

  try {
    const data = await apiRequest(`/api/screen/${jobId}/questions/${resumeId}`);
    if (!data.questions?.length) {
      body.innerHTML = "<p>暂无试题</p>";
      return;
    }
    body.innerHTML = data.questions
      .map(
        (q, i) => `
      <div class="question-card">
        <div class="q-head"><span class="q-num">Q${i + 1}</span>
          <span class="badge badge-muted">${escapeHtml(q.category)} · ${escapeHtml(q.difficulty)}</span></div>
        <p class="q-text">${escapeHtml(q.question)}</p>
        <p class="muted small"><strong>考察点：</strong>${escapeHtml(q.competency)}</p>
        <p class="muted small"><strong>评分标准：</strong>${escapeHtml(q.rubric)}</p>
      </div>`
      )
      .join("");
    loadResults();
  } catch (err) {
    body.innerHTML = `<p style="color:var(--danger)">${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("refresh-btn").addEventListener("click", loadResults);
document.getElementById("close-questions").addEventListener("click", () => {
  questionDrawer.style.display = "none";
});

document.getElementById("cancel-interview").addEventListener("click", () => {
  modal.style.display = "none";
  pendingResumeId = null;
});

document.getElementById("persona-select").addEventListener("change", (e) => {
  const enc = document.getElementById("enable-encouragement");
  enc.checked = e.target.value === "hr_friendly";
});

document.getElementById("strictness-range").addEventListener("input", (e) => {
  document.getElementById("strictness-val").textContent = e.target.value;
});
document.getElementById("warmth-range").addEventListener("input", (e) => {
  document.getElementById("warmth-val").textContent = e.target.value;
});

function buildInterviewConfig() {
  const persona = document.getElementById("persona-select").value;
  return {
    interview_mode: document.getElementById("mode-select").value,
    persona,
    role_title: document.getElementById("role-title").value.trim(),
    strictness: Number(document.getElementById("strictness-range").value),
    warmth: Number(document.getElementById("warmth-range").value),
    difficulty: document.getElementById("difficulty-select").value,
    max_followup_streak: Number(document.getElementById("followup-max").value),
    enable_encouragement: document.getElementById("enable-encouragement").checked,
    standardized_question_limit: 5,
  };
}

document.getElementById("confirm-interview").addEventListener("click", async () => {
  if (!pendingResumeId) return;
  const persona = document.getElementById("persona-select").value;
  const config = buildInterviewConfig();
  const btn = document.getElementById("confirm-interview");
  btn.disabled = true;

  try {
    const session = await apiRequest("/api/interview/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: Number(jobId),
        resume_id: Number(pendingResumeId),
        persona,
        config,
      }),
    });
    const mode = session.interview_mode || config.interview_mode;
    window.location.href = `/interview.html?session_id=${session.session_id}&persona=${persona}&mode=${mode}`;
  } catch (err) {
    showToast(err.message, true);
    btn.disabled = false;
  }
});

loadResults();
