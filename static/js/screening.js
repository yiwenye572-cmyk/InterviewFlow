import { showToast, apiRequest, getQueryParam, scoreClass } from "/static/js/api.js";

const jobId = getQueryParam("job_id");
let pendingResumeId = null;

const modal = document.getElementById("persona-modal");
modal.style.display = "none";

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

    const rows = data.results.map((r) => {
      const badge = r.can_interview
        ? '<span class="badge badge-success">推荐面试</span>'
        : '<span class="badge badge-muted">暂不推荐</span>';
      const reasons = r.reasons.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
      const interviewBtn = r.can_interview
        ? `<button class="btn btn-primary btn-sm start-interview" data-resume-id="${r.resume_id}">开始面试</button>`
        : `<button class="btn btn-secondary" disabled>不可面试</button>`;

      return `
        <tr>
          <td>
            <strong>${escapeHtml(r.candidate_name)}</strong><br/>
            <small style="color:var(--muted)">${escapeHtml(r.filename)}</small>
          </td>
          <td><span class="score ${scoreClass(r.final_score)}">${r.final_score}</span></td>
          <td>${r.semantic_score.toFixed(1)} / ${r.llm_score.toFixed(1)}</td>
          <td>${badge}<ul style="margin-top:0.5rem;font-size:0.85rem">${reasons}</ul></td>
          <td>${interviewBtn}</td>
        </tr>`;
    }).join("");

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

    document.querySelectorAll(".start-interview").forEach((btn) => {
      btn.addEventListener("click", () => {
        pendingResumeId = btn.dataset.resumeId;
        modal.style.display = "flex";
      });
    });
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger)">${escapeHtml(err.message)}</p>`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

document.getElementById("refresh-btn").addEventListener("click", loadResults);

document.getElementById("cancel-interview").addEventListener("click", () => {
  modal.style.display = "none";
  pendingResumeId = null;
});

document.getElementById("confirm-interview").addEventListener("click", async () => {
  if (!pendingResumeId) return;
  const persona = document.getElementById("persona-select").value;
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
      }),
    });
    window.location.href = `/interview.html?session_id=${session.session_id}&persona=${persona}`;
  } catch (err) {
    showToast(err.message, true);
    btn.disabled = false;
  }
});

loadResults();
