import { pageUrl } from "./api.js";

const STEP_DEFS = [
  { num: 1, label: "上传", href: () => pageUrl("/") },
  {
    num: 2,
    label: "筛选",
    href: (ctx) => (ctx.jobId ? pageUrl(`/screening.html?job_id=${ctx.jobId}`) : null),
  },
  {
    num: 3,
    label: "面试",
    href: (ctx) =>
      ctx.sessionId
        ? pageUrl(
            `/interview.html?session_id=${ctx.sessionId}${ctx.jobId ? `&job_id=${ctx.jobId}` : ""}`,
          )
        : null,
  },
  {
    num: 4,
    label: "报告",
    href: (ctx) =>
      ctx.sessionId
        ? pageUrl(
            `/report.html?session_id=${ctx.sessionId}${ctx.jobId ? `&job_id=${ctx.jobId}` : ""}`,
          )
        : null,
  },
];

const STEP_CHECK_SVG = `<svg class="flow-step__icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`;

function stepStatus(stepNum, currentStep) {
  if (stepNum < currentStep) return "done";
  if (stepNum === currentStep) return "current";
  return "pending";
}

function renderFlowStepper(currentStep, ctx) {
  const items = STEP_DEFS.map((step, idx) => {
    const status = stepStatus(step.num, currentStep);
    const href = step.href(ctx);
    const dot =
      status === "done"
        ? STEP_CHECK_SVG
        : `<span class="flow-step__num">${step.num}</span>`;
    const label = `<span class="flow-step__label">${step.label}</span>`;
    const body = `<span class="flow-step__dot">${dot}</span>${label}`;

    let stepHtml;
    if (status === "done" && href) {
      stepHtml = `<a href="${href}" class="flow-step__link" data-nav-link="step" aria-label="${step.label}（已完成，点击返回）">${body}</a>`;
    } else if (status === "current") {
      stepHtml = `<span class="flow-step__link" aria-label="${step.label}，当前步骤">${body}</span>`;
    } else {
      stepHtml = `<span class="flow-step__link" aria-label="${step.label}（未完成）">${body}</span>`;
    }

    const currentAttr = status === "current" ? ' aria-current="step"' : "";
    let html = `<li class="flow-step flow-step--${status}"${currentAttr}>${stepHtml}</li>`;

    if (idx < STEP_DEFS.length - 1) {
      const nextNum = STEP_DEFS[idx + 1].num;
      const joinDone = nextNum <= currentStep;
      html += `<li class="flow-step-join${joinDone ? " flow-step-join--done" : ""}" aria-hidden="true"></li>`;
    }
    return html;
  }).join("");

  return `<div class="flow-stepper-card">
    <nav class="flow-stepper" aria-label="招聘流程进度">
      <ol class="flow-stepper__track">${items}</ol>
    </nav>
  </div>`;
}

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
      <a href="${pageUrl("/")}" class="app-nav-brand" data-nav-link="home">AI 招聘助手</a>
      <div class="app-nav-links">
        <a href="${pageUrl("/")}" data-nav-link="home">首页</a>
        <a href="${pageUrl("/history.html")}">完整历史</a>
      </div>
    </div>`;

  const stepsHtml =
    currentStep != null ? renderFlowStepper(currentStep, ctx) : "";

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
  return jobId ? pageUrl(`/screening.html?job_id=${jobId}`) : pageUrl("/screening.html");
}
