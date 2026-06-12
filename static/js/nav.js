const STEP_DEFS = [
  { num: 1, label: "1. 上传", href: () => "/" },
  {
    num: 2,
    label: "2. 筛选",
    href: (ctx) => (ctx.jobId ? `/screening.html?job_id=${ctx.jobId}` : null),
  },
  {
    num: 3,
    label: "3. 面试",
    href: (ctx) =>
      ctx.sessionId
        ? `/interview.html?session_id=${ctx.sessionId}${ctx.jobId ? `&job_id=${ctx.jobId}` : ""}`
        : null,
  },
  {
    num: 4,
    label: "4. 报告",
    href: (ctx) =>
      ctx.sessionId
        ? `/report.html?session_id=${ctx.sessionId}${ctx.jobId ? `&job_id=${ctx.jobId}` : ""}`
        : null,
  },
];

let navState = {
  confirmLeave: false,
  sessionActive: false,
  leaveMessage:
    "面试进行中，确定离开？未结束的会话可在岗位详情中继续。",
};

let beforeUnloadBound = false;

function bindBeforeUnloadOnce() {
  if (beforeUnloadBound) return;
  beforeUnloadBound = true;
  window.addEventListener("beforeunload", (e) => {
    if (!navState.confirmLeave || !navState.sessionActive) return;
    e.preventDefault();
    e.returnValue = "";
  });
}

export function navigateWithConfirm(href, message) {
  if (!href) return;
  const msg = message || navState.leaveMessage;
  if (navState.confirmLeave && navState.sessionActive) {
    if (!confirm(msg)) return;
  }
  window.location.href = href;
}

export function setNavSessionActive(active) {
  navState.sessionActive = active;
}

export function initAppNav(options = {}) {
  const mount = document.getElementById("app-nav");
  if (!mount) return;

  const currentStep = options.currentStep ?? null;
  const ctx = {
    jobId: options.jobId ?? null,
    sessionId: options.sessionId ?? null,
  };

  navState.confirmLeave = Boolean(options.confirmLeave);
  navState.sessionActive = Boolean(options.sessionActive);

  const globalBar = `
    <div class="app-nav-global">
      <a href="/" class="app-nav-brand" data-nav-link="home">AI 招聘助手</a>
      <div class="app-nav-links">
        <a href="/" data-nav-link="home">首页</a>
        <a href="/history.html">完整历史</a>
      </div>
    </div>`;

  let stepsHtml = "";
  if (currentStep != null) {
    stepsHtml = `<nav class="steps app-steps">${STEP_DEFS.map((step) => {
      const href = step.href(ctx);
      if (step.num === currentStep) {
        return `<span class="step active">${step.label}</span>`;
      }
      if (step.num < currentStep) {
        if (href) {
          return `<a class="step clickable" href="${href}" data-nav-link="step">${step.label}</a>`;
        }
        return `<span class="step disabled">${step.label}</span>`;
      }
      return `<span class="step disabled">${step.label}</span>`;
    }).join("")}</nav>`;
  }

  let actionsHtml = "";
  const extras = options.extraActions || [];
  if (options.back || extras.length) {
    const backBtn = options.back
      ? `<a href="${options.back.href}" class="btn btn-secondary page-nav-back" data-nav-link="back">← ${options.back.label}</a>`
      : "";
    const extraBtns = extras
      .map((a) => {
        if (a.type === "button") {
          return `<button type="button" class="btn ${a.primary ? "btn-primary" : "btn-secondary"}"${a.id ? ` id="${a.id}"` : ""}>${a.label}</button>`;
        }
        return `<a href="${a.href}" class="btn ${a.primary ? "btn-primary" : "btn-secondary"}"${a.id ? ` id="${a.id}"` : ""}${a.navLink ? ` data-nav-link="${a.navLink}"` : ""}>${a.label}</a>`;
      })
      .join("");
    actionsHtml = `<div class="page-nav-actions">${backBtn}${extraBtns}</div>`;
  }

  mount.innerHTML = globalBar + stepsHtml + actionsHtml;

  (options.extraActions || []).forEach((action) => {
    if (action.type === "button" && action.id && typeof action.onClick === "function") {
      document.getElementById(action.id)?.addEventListener("click", action.onClick);
    }
  });

  if (navState.confirmLeave) {
    bindBeforeUnloadOnce();
    mount.querySelectorAll("[data-nav-link]").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (!navState.sessionActive) return;
        e.preventDefault();
        navigateWithConfirm(el.getAttribute("href"));
      });
    });
  }
}

export function screeningHref(jobId) {
  return jobId ? `/screening.html?job_id=${jobId}` : "/screening.html";
}
