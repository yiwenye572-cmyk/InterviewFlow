import { apiRequest } from "/static/js/api.js";

const container = document.getElementById("jobs-container");

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

async function loadJobs() {
  try {
    const data = await apiRequest("/api/jobs");
    const jobs = data.jobs || [];
    if (!jobs.length) {
      container.innerHTML = "<p>暂无历史岗位，请先<a href='/'>上传 JD</a>。</p>";
      return;
    }

    const rows = jobs.map(
      (j) => `
      <tr class="clickable-row" data-job-id="${j.id}">
        <td><strong>${escapeHtml(j.title)}</strong><br/><small class="muted">${escapeHtml(j.filename)}</small></td>
        <td>${j.resume_count}</td>
        <td>${j.interview_count} <small class="muted">(${j.completed_interview_count} 已完成)</small></td>
        <td>${formatDate(j.created_at)}</td>
        <td><a href="/job.html?job_id=${j.id}" class="btn btn-secondary btn-sm">详情</a></td>
      </tr>`
    ).join("");

    container.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>岗位</th>
            <th>简历数</th>
            <th>面试数</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;

    document.querySelectorAll(".clickable-row").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest("a")) return;
        window.location.href = `/job.html?job_id=${row.dataset.jobId}`;
      });
    });
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger)">${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("refresh-btn").addEventListener("click", loadJobs);
loadJobs();
