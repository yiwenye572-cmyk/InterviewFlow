import { showToast, apiRequest } from "/static/js/api.js";
import { initAppNav } from "/static/js/nav.js";

const STORAGE_KEY = "selectedJobId";

const jobListEl = document.getElementById("job-list");
const panelNew = document.getElementById("panel-new");
const panelExisting = document.getElementById("panel-existing");
const selectedTitle = document.getElementById("selected-job-title");
const selectedMeta = document.getElementById("selected-job-meta");
const selectedSummary = document.getElementById("selected-job-summary");
const resumeListEl = document.getElementById("resume-list");
const selectAllEl = document.getElementById("select-all-resumes");
const uploadAndScreenBtn = document.getElementById("upload-and-screen-btn");
const enterScreenBtn = document.getElementById("enter-screen-btn");
const submitNewBtn = document.getElementById("submit-new-btn");
const resumeFileInput = document.getElementById("resume-files-existing");

let jobs = [];
let resumes = [];
let selectedJobId = null;
let mode = "new";

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "";
  }
}

function setMode(next) {
  mode = next;
  panelNew.classList.toggle("hidden", mode !== "new");
  panelExisting.classList.toggle("hidden", mode !== "existing");
  document.querySelectorAll(".job-list-row").forEach((el) => {
    el.classList.toggle("active", mode === "existing" && Number(el.dataset.jobId) === selectedJobId);
  });
}

function getSelectedJob() {
  return jobs.find((j) => j.id === selectedJobId) || null;
}

function getSelectedResumeIds() {
  return [...resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]:checked')].map(
    (el) => Number(el.dataset.resumeId)
  );
}

function hasPendingUploads() {
  return resumeFileInput.files.length > 0;
}

function updateScreenButton() {
  const ids = getSelectedResumeIds();
  uploadAndScreenBtn.disabled = !hasPendingUploads() && ids.length === 0;
}

function applyCheckedResumeIds(ids) {
  const idSet = new Set(ids);
  resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]').forEach((cb) => {
    cb.checked = idSet.has(Number(cb.dataset.resumeId));
  });
  const all = resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]');
  selectAllEl.checked = all.length > 0 && [...all].every((x) => x.checked);
  updateScreenButton();
}

function updateExistingPanel() {
  const job = getSelectedJob();
  if (!job) {
    setMode("new");
    return;
  }
  selectedTitle.textContent = job.title || job.filename;
  const structuredTag = job.has_structured ? "已解析" : "待解析";
  selectedMeta.textContent = `${job.filename} · ${structuredTag} · ${formatDate(job.created_at)}`;
  selectedSummary.textContent = job.jd_summary || "（暂无摘要）";
  const hasScreened = resumes.some((r) => r.screened);
  enterScreenBtn.classList.toggle("hidden", !hasScreened);
}

function renderResumeList() {
  if (!resumes.length) {
    resumeListEl.innerHTML = '<p class="muted">暂无简历，请选择文件后点击「上传并筛选」。</p>';
    selectAllEl.checked = false;
    selectAllEl.disabled = true;
    updateScreenButton();
    return;
  }

  selectAllEl.disabled = false;
  resumeListEl.innerHTML = resumes
    .map(
      (r) => `
    <label class="resume-select-item">
      <input type="checkbox" data-resume-id="${r.resume_id}" ${r.screened ? "" : "checked"} />
      <span class="resume-select-body">
        <strong>${escapeHtml(r.candidate_name)}</strong>
        <span class="muted">${escapeHtml(r.filename)}</span>
        ${r.screened ? `<span class="badge badge-muted">已筛选 ${r.final_score ?? "—"} 分</span>` : `<span class="badge badge-warning">${escapeHtml(r.parse_status)}</span>`}
      </span>
    </label>`
    )
    .join("");

  resumeListEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const all = resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]');
      selectAllEl.checked = [...all].every((x) => x.checked);
      updateScreenButton();
    });
  });

  const all = resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]');
  selectAllEl.checked = all.length > 0 && [...all].every((x) => x.checked);
  updateScreenButton();
}

async function loadResumesForJob(jobId) {
  if (!jobId) {
    resumes = [];
    renderResumeList();
    return;
  }
  try {
    const data = await apiRequest(`/api/jobs/${jobId}/resumes`);
    resumes = data.resumes || [];
    renderResumeList();
    updateExistingPanel();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function selectJob(id) {
  selectedJobId = id;
  localStorage.setItem(STORAGE_KEY, String(id));
  setMode("existing");
  await loadJobSidebar();
  await loadResumesForJob(id);
  updateExistingPanel();
}

function renderJobList() {
  if (!jobs.length) {
    jobListEl.innerHTML = '<p class="muted">暂无岗位，请点击「新建」上传 JD。</p>';
    setMode("new");
    return;
  }

  jobListEl.innerHTML = jobs
    .map(
      (j) => `
    <div class="job-list-row${selectedJobId === j.id && mode === "existing" ? " active" : ""}" data-job-id="${j.id}">
      <button type="button" class="job-list-item" data-job-id="${j.id}">
        <span class="job-list-title">${escapeHtml(j.title || j.filename)}</span>
        <span class="job-list-meta muted">${j.resume_count} 份简历 · ${formatDate(j.created_at)}</span>
        ${j.jd_summary ? `<span class="job-list-summary">${escapeHtml(j.jd_summary.slice(0, 60))}${j.jd_summary.length > 60 ? "…" : ""}</span>` : ""}
      </button>
      <button type="button" class="job-delete-btn" data-job-id="${j.id}" title="删除岗位" aria-label="删除岗位">×</button>
    </div>`
    )
    .join("");

  jobListEl.querySelectorAll(".job-list-item").forEach((btn) => {
    btn.addEventListener("click", () => selectJob(Number(btn.dataset.jobId)));
  });

  jobListEl.querySelectorAll(".job-delete-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.jobId);
      const job = jobs.find((j) => j.id === id);
      deleteJob(id, job?.title || job?.filename);
    });
  });
}

async function deleteJob(id, title) {
  const name = title || `岗位 #${id}`;
  if (
    !confirm(
      `确定删除「${name}」？\n将同时删除该岗位下的简历、筛选与面试记录，且不可恢复。`
    )
  ) {
    return;
  }

  try {
    await apiRequest(`/api/jobs/${id}`, { method: "DELETE" });
    showToast("岗位已删除");
    if (selectedJobId === id) {
      selectedJobId = null;
      resumes = [];
      localStorage.removeItem(STORAGE_KEY);
      renderResumeList();
      setMode("new");
    }
    await loadJobSidebar();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadJobSidebar() {
  try {
    const data = await apiRequest("/api/jobs");
    jobs = data.jobs || [];
    renderJobList();

    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && jobs.some((j) => j.id === Number(saved)) && !selectedJobId) {
      await selectJob(Number(saved));
    }
  } catch (err) {
    jobListEl.innerHTML = `<p class="muted" style="color:var(--danger)">${escapeHtml(err.message)}</p>`;
    showToast(err.message, true);
  }
}

async function createNewJob() {
  const jdFile = document.getElementById("jd-file").files[0];
  if (!jdFile) {
    showToast("请先上传 JD 文件", true);
    return;
  }

  submitNewBtn.disabled = true;
  submitNewBtn.innerHTML = '<span class="spinner"></span> 解析中...';

  try {
    const jdForm = new FormData();
    jdForm.append("file", jdFile);
    const job = await apiRequest("/api/jobs", { method: "POST", body: jdForm });
    document.getElementById("jd-file").value = "";
    showToast("岗位已创建，请上传并筛选简历");
    selectedJobId = job.id;
    localStorage.setItem(STORAGE_KEY, String(job.id));
    await loadJobSidebar();
    setMode("existing");
    await loadResumesForJob(job.id);
    updateExistingPanel();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    submitNewBtn.disabled = false;
    submitNewBtn.textContent = "创建岗位";
  }
}

async function uploadAndScreen() {
  if (!selectedJobId) {
    showToast("请先在左侧选择岗位", true);
    return;
  }

  const existingIds = new Set(resumes.map((r) => r.resume_id));
  let idsToScreen = getSelectedResumeIds();
  const hasFiles = hasPendingUploads();

  if (!hasFiles && !idsToScreen.length) {
    showToast("请至少选择一份简历或上传新文件", true);
    return;
  }

  uploadAndScreenBtn.disabled = true;
  uploadAndScreenBtn.innerHTML = '<span class="spinner"></span> 处理中...';

  try {
    if (hasFiles) {
      const form = new FormData();
      for (const f of resumeFileInput.files) form.append("files", f);
      await apiRequest(`/api/resumes?job_id=${selectedJobId}`, { method: "POST", body: form });
      resumeFileInput.value = "";
      await loadJobSidebar();
      await loadResumesForJob(selectedJobId);

      const newIds = resumes.filter((r) => !existingIds.has(r.resume_id)).map((r) => r.resume_id);
      idsToScreen = [...new Set([...idsToScreen, ...newIds])];
      applyCheckedResumeIds(idsToScreen);
    }

    idsToScreen = getSelectedResumeIds();
    if (!idsToScreen.length) {
      showToast("请至少勾选一份要筛选的简历", true);
      return;
    }

    uploadAndScreenBtn.innerHTML = '<span class="spinner"></span> 筛选中...';
    await apiRequest(`/api/screen/${selectedJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_ids: idsToScreen }),
    });
    window.location.href = `/screening.html?job_id=${selectedJobId}`;
  } catch (err) {
    showToast(err.message, true);
    uploadAndScreenBtn.disabled = false;
    uploadAndScreenBtn.textContent = "上传并筛选";
    updateScreenButton();
  }
}

function enterScreening() {
  if (!selectedJobId) return;
  window.location.href = `/screening.html?job_id=${selectedJobId}`;
}

document.getElementById("new-job-btn").addEventListener("click", () => {
  selectedJobId = null;
  resumes = [];
  renderResumeList();
  localStorage.removeItem(STORAGE_KEY);
  setMode("new");
  renderJobList();
});

selectAllEl.addEventListener("change", () => {
  resumeListEl.querySelectorAll('input[type="checkbox"][data-resume-id]').forEach((cb) => {
    cb.checked = selectAllEl.checked;
  });
  updateScreenButton();
});

resumeFileInput.addEventListener("change", updateScreenButton);

submitNewBtn.addEventListener("click", createNewJob);
uploadAndScreenBtn.addEventListener("click", uploadAndScreen);
enterScreenBtn.addEventListener("click", enterScreening);

loadJobSidebar();
initAppNav({ currentStep: 1 });
