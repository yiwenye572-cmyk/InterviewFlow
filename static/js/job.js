import { apiRequest, getQueryParam, recommendationClass, scoreClass } from "/static/js/api.js";

const jobId = getQueryParam("job_id");

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const modeLabel = { adaptive: "自适应", standardized: "标准化" };
const personaLabel = { tech_lead: "技术总监", hr_friendly: "HR" };

async function loadOverview() {
  if (!jobId) {
    document.getElementById("jd-summary").textContent = "缺少 job_id";
    return;
  }

  document.getElementById("screen-link").href = `/screening.html?job_id=${jobId}`;

  try {
    const data = await apiRequest(`/api/jobs/${jobId}/overview`);
    document.getElementById("job-title").textContent = data.job.title;
    document.getElementById("job-subtitle").textContent = data.job.filename;
    document.getElementById("jd-summary").textContent = data.jd_summary || "暂无结构化摘要";

    const container = document.getElementById("interviews-container");
    const interviews = data.interviews || [];

    if (!interviews.length) {
      container.innerHTML = "<h2>面试记录</h2><p class='muted'>暂无面试，请从筛选页发起模拟面试。</p>";
      return;
    }

    const rows = interviews.map((i) => {
      const rec = i.overall_recommendation
        ? `<span class="recommendation ${recommendationClass(i.overall_recommendation)}">${escapeHtml(i.overall_recommendation)}</span>`
        : `<span class="badge badge-muted">${escapeHtml(i.status)}</span>`;
      const score = i.job_fit_score != null
        ? `<span class="score ${scoreClass(i.job_fit_score)}">${i.job_fit_score}</span>`
        : "—";
      const reportBtn = i.status === "completed"
        ? `<a href="/report.html?session_id=${i.session_id}" class="btn btn-primary btn-sm">查看报告</a>`
        : `<a href="/interview.html?session_id=${i.session_id}&persona=${i.persona}" class="btn btn-secondary btn-sm">继续面试</a>`;

      return `
        <tr>
          <td>${escapeHtml(i.candidate_name)}</td>
          <td>${personaLabel[i.persona] || i.persona}</td>
          <td>${modeLabel[i.interview_mode] || i.interview_mode}</td>
          <td>${score}</td>
          <td>${rec}</td>
          <td><small>${escapeHtml(i.report_summary || "—")}</small></td>
          <td>${formatDate(i.created_at)}</td>
          <td>${reportBtn}</td>
        </tr>`;
    }).join("");

    container.innerHTML = `
      <h2>面试记录 (${interviews.length})</h2>
      <table>
        <thead>
          <tr>
            <th>候选人</th>
            <th>人设</th>
            <th>模式</th>
            <th>匹配分</th>
            <th>决策</th>
            <th>简述</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    document.getElementById("jd-summary").textContent = err.message;
  }
}

loadOverview();
