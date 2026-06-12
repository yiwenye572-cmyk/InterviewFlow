import { showToast, apiRequest, getQueryParam } from "/static/js/api.js";
import { initAppNav, setNavSessionActive } from "/static/js/nav.js";
import {
  startRecording,
  stopRecording,
  isRecordingSupported,
} from "/static/js/wav-recorder.js";

const sessionId = getQueryParam("session_id");
const persona = getQueryParam("persona") || "tech_lead";
let jobId = getQueryParam("job_id");

const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const endBtn = document.getElementById("end-btn");
const typingIndicator = document.getElementById("typing-indicator");
const liveContent = document.getElementById("live-content");
const agendaContent = document.getElementById("agenda-content");
const textInputRow = document.getElementById("text-input-row");
const voiceInputRow = document.getElementById("voice-input-row");
const holdTalkBtn = document.getElementById("hold-talk-btn");
const voiceStatus = document.getElementById("voice-status");
const transportRadios = document.querySelectorAll('input[name="transport"]');

let isStreaming = false;
let roundCount = 0;
let transportMode = "text";
let isRecording = false;
let currentAudio = null;

const personaLabel = {
  tech_lead: "严厉的技术总监",
  hr_friendly: "亲切的 HR",
};

const phaseLabel = {
  opening: "开场",
  technical: "技术",
  project: "项目",
  behavioral: "行为",
  closing: "收尾",
};

const modeLabel = {
  adaptive: "自适应",
  standardized: "标准化",
};

const difficultyLabel = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
};

const pendingActionLabel = {
  stream_opening: "生成开场",
  stream_question: "下一题",
  stream_followup: "追问",
  stream_closing: "收尾",
  stream_encouragement: "鼓励话术",
  wait_answer: "等待回答",
  generate_report: "生成报告",
  plan_topic: "规划议题",
};

const competencyStatusLabel = {
  covered: "已验证",
  at_risk: "存疑",
  uncovered: "未覆盖",
};

const urlMode = getQueryParam("mode");
document.getElementById("meta-persona").textContent =
  `面试官：${personaLabel[persona] || persona}`;
if (urlMode) {
  document.getElementById("meta-mode").textContent =
    `模式：${modeLabel[urlMode] || urlMode}`;
}

function appendMessage(role, content, streaming = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;
  if (streaming) div.dataset.streaming = "true";
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function appendSystem(text) {
  appendMessage("system", text);
}

function setTyping(active) {
  typingIndicator.classList.toggle("hidden", !active);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function renderLiveAssessment(live) {
  if (!live) return;
  liveContent.innerHTML = `
    <div class="live-scores">
      <div class="live-score-item">
        <span class="label">岗位匹配（预估）</span>
        <span class="value">${live.provisional_job_fit ?? "—"}</span>
      </div>
      <div class="live-score-item">
        <span class="label">沟通能力</span>
        <span class="value">${live.provisional_communication ?? "—"}</span>
      </div>
    </div>
    <div class="live-section">
      <h4>观察到的优势</h4>
      <ul>${(live.observed_strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("") || "<li>暂无</li>"}</ul>
    </div>
    <div class="live-section">
      <h4>潜在风险</h4>
      <ul>${(live.observed_risks || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("") || "<li>暂无</li>"}</ul>
    </div>
    <p class="live-updated">置信度：${live.score_confidence != null ? (live.score_confidence * 100).toFixed(0) + "%" : "—"} · 更新：${live.last_updated ? new Date(live.last_updated).toLocaleString() : "—"}</p>`;
}

function renderAgendaPanel(status) {
  if (!status || !agendaContent) return;
  const phase = phaseLabel[status.phase] || status.phase || "—";
  const action =
    pendingActionLabel[status.pending_action] || status.pending_action || "—";
  const topic = status.current_topic || "（暂无）";
  const followups = status.followup_queue || [];
  const upcoming = status.upcoming_questions || [];
  const compStatus = status.competency_status || {};

  const followupHtml = followups.length
    ? `<ol class="agenda-list">${followups
        .map((q) => `<li>${escapeHtml(q)}</li>`)
        .join("")}</ol>`
    : `<p class="muted small">暂无待追问</p>`;

  const upcomingHtml = upcoming.length
    ? upcoming
        .map(
          (q, i) => `
      <div class="agenda-question-card">
        <span class="badge badge-muted">${escapeHtml(q.category || "题目")} · ${escapeHtml(q.difficulty || "—")}</span>
        <p><strong>Q${(status.question_index || 0) + i + 1}.</strong> ${escapeHtml(q.question)}</p>
        <p class="muted small">考察：${escapeHtml(q.competency || "—")}</p>
      </div>`
        )
        .join("")
    : `<p class="muted small">暂无排队主题目</p>`;

  const compKeys = Object.keys(compStatus);
  const compHtml = compKeys.length
    ? `<ul class="agenda-comp-list">${compKeys
        .map(
          (k) =>
            `<li><span class="comp-badge comp-${compStatus[k]}">${competencyStatusLabel[compStatus[k]] || compStatus[k]}</span> ${escapeHtml(k)}</li>`
        )
        .join("")}</ul>`
    : `<p class="muted small">暂无考察点计划</p>`;

  agendaContent.innerHTML = `
    <div class="agenda-section">
      <h4>当前状态</h4>
      <p class="agenda-meta"><span>阶段：${escapeHtml(phase)}</span> · <span>动作：${escapeHtml(action)}</span></p>
      <p class="agenda-topic"><strong>当前议题：</strong>${escapeHtml(topic)}</p>
    </div>
    <div class="agenda-section">
      <h4>待追问队列</h4>
      ${followupHtml}
    </div>
    <div class="agenda-section">
      <h4>主题目预告</h4>
      ${upcomingHtml}
    </div>
    <div class="agenda-section">
      <h4>考察点覆盖</h4>
      ${compHtml}
    </div>`;
}

function reportUrl() {
  const q = jobId ? `&job_id=${jobId}` : "";
  return `/report.html?session_id=${sessionId}${q}`;
}

function screeningBackHref() {
  return jobId ? `/screening.html?job_id=${jobId}` : "/";
}

function setupInterviewNav(status) {
  if (status?.job_id && !jobId) {
    jobId = String(status.job_id);
  }
  const active = status?.status === "active";
  setNavSessionActive(active);
  initAppNav({
    currentStep: 3,
    jobId: jobId ? Number(jobId) : null,
    sessionId: sessionId ? Number(sessionId) : null,
    confirmLeave: true,
    sessionActive: active,
    back: { label: "返回筛选", href: screeningBackHref() },
  });
}

function updateMeta(status) {
  if (status.interview_mode) {
    document.getElementById("meta-mode").textContent =
      `模式：${modeLabel[status.interview_mode] || status.interview_mode}`;
  }
  const cfg = status.interview_config || {};
  if (cfg.difficulty) {
    document.getElementById("meta-difficulty").textContent =
      `难度：${difficultyLabel[cfg.difficulty] || cfg.difficulty}`;
  }
  if (status.phase) {
    document.getElementById("meta-phase").textContent =
      `阶段：${phaseLabel[status.phase] || status.phase}`;
  }
  if (typeof status.round_count === "number") {
    roundCount = status.round_count;
    document.getElementById("meta-round").textContent = `轮次：${roundCount}`;
  }
  const statusMap = status.competency_status || {};
  const counts = { covered: 0, at_risk: 0, uncovered: 0 };
  Object.values(statusMap).forEach((v) => {
    if (counts[v] !== undefined) counts[v]++;
  });
  const total = Object.keys(statusMap).length || status.competencies_planned?.length || 0;
  document.getElementById("meta-competencies").textContent =
    `考察点：已验证 ${counts.covered} / 存疑 ${counts.at_risk} / 未覆盖 ${counts.uncovered || Math.max(0, total - counts.covered - counts.at_risk)}`;
}

async function refreshStatus() {
  if (!sessionId) return null;
  try {
    const status = await apiRequest(`/api/interview/${sessionId}/status`);
    updateMeta(status);
    renderAgendaPanel(status);
    setupInterviewNav(status);
    return status;
  } catch {
    return null;
  }
}

async function refreshLive() {
  if (!sessionId) return;
  try {
    const live = await apiRequest(`/api/interview/${sessionId}/live`);
    renderLiveAssessment(live);
  } catch {
    /* not available yet */
  }
}

async function restoreMessages() {
  if (!sessionId) return;
  try {
    const data = await apiRequest(`/api/interview/${sessionId}/messages`);
    if (data.messages?.length) {
      chatWindow.innerHTML = "";
      for (const msg of data.messages) {
        if (msg.role === "assistant" || msg.role === "user") {
          appendMessage(msg.role, msg.content);
        }
      }
      appendSystem("已恢复历史对话");
    }
  } catch {
    /* fresh session */
  }
}

async function consumeStream() {
  if (!sessionId || transportMode === "voice") return;
  isStreaming = true;
  sendBtn.disabled = true;
  setTyping(true);

  const bubble = appendMessage("assistant", "", true);

  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/interview/${sessionId}/stream`);

    source.addEventListener("message", (event) => {
      let chunk = event.data;
      try {
        chunk = JSON.parse(chunk);
      } catch {
        /* plain string */
      }
      if (chunk === "[DONE]") return;
      bubble.textContent += chunk;
      chatWindow.scrollTop = chatWindow.scrollHeight;
    });

    source.addEventListener("done", () => {
      source.close();
      delete bubble.dataset.streaming;
      isStreaming = false;
      sendBtn.disabled = false;
      setTyping(false);
      resolve();
    });

    source.addEventListener("error", (event) => {
      source.close();
      isStreaming = false;
      sendBtn.disabled = false;
      setTyping(false);
      if (event.data) {
        try {
          const msg = JSON.parse(event.data);
          showToast(msg, true);
        } catch {
          showToast("流式连接出错", true);
        }
      }
      reject(new Error("stream error"));
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return;
      source.close();
      isStreaming = false;
      sendBtn.disabled = false;
      setTyping(false);
    };
  });
}

function setTransportMode(mode) {
  transportMode = mode;
  const isVoice = mode === "voice";
  textInputRow.classList.toggle("hidden", isVoice);
  voiceInputRow.classList.toggle("hidden", !isVoice);
  voiceStatus.classList.toggle("hidden", !isVoice);
  if (isVoice && !isRecordingSupported()) {
    voiceStatus.textContent = "当前浏览器不支持录音";
  } else if (isVoice) {
    voiceStatus.textContent = "按住按钮说话，松手发送";
  }
}

function playAssistantAudio(base64, mime = "audio/mpeg") {
  if (!base64) return;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  currentAudio = new Audio(`data:${mime};base64,${base64}`);
  currentAudio.play().catch(() => {
    showToast("无法播放语音", true);
  });
}

async function sendVoiceTurn(wavBlob) {
  if (!sessionId || isStreaming) return;

  isStreaming = true;
  holdTalkBtn.disabled = true;
  sendBtn.disabled = true;
  setTyping(true);
  voiceStatus.textContent = "识别与回复中…";

  const form = new FormData();
  form.append("file", wavBlob, "utterance.wav");

  try {
    const response = await fetch(`/api/interview/${sessionId}/voice/turn`, {
      method: "POST",
      body: form,
    });
    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }
    if (!response.ok) {
      const detail = data?.detail || (typeof data === "string" ? data : "Voice turn failed");
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    appendMessage("user", data.transcript || "（语音）");
    appendMessage("assistant", data.assistant_text || "");
    playAssistantAudio(data.audio_base64, data.audio_mime || "audio/mpeg");

    updateMeta(data);
    if (data.live_assessment) {
      renderLiveAssessment(data.live_assessment);
    } else {
      await refreshLive();
    }
    await refreshStatus();

    const closing =
      data.pending_action === "stream_closing" ||
      data.pending_action === "generate_report";

    if (closing) {
      appendSystem("面试即将结束...");
      appendSystem("正在生成评估报告...");
      await apiRequest(`/api/interview/${sessionId}/end`, { method: "POST" });
      window.location.href = reportUrl();
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    isStreaming = false;
    holdTalkBtn.disabled = false;
    sendBtn.disabled = false;
    setTyping(false);
    if (transportMode === "voice") {
      voiceStatus.textContent = "按住按钮说话，松手发送";
    }
  }
}

async function onHoldTalkStart(event) {
  event.preventDefault();
  if (isStreaming || isRecording) return;
  try {
    await startRecording();
    isRecording = true;
    holdTalkBtn.classList.add("recording");
    voiceStatus.textContent = "录音中…松手发送";
  } catch (err) {
    showToast("无法访问麦克风：" + err.message, true);
  }
}

async function onHoldTalkEnd(event) {
  event.preventDefault();
  if (!isRecording) return;
  isRecording = false;
  holdTalkBtn.classList.remove("recording");
  voiceStatus.textContent = "处理中…";
  try {
    const { blob: wavBlob, peak, durationSec } = await stopRecording();
    if (!wavBlob || wavBlob.size < 1000) {
      voiceStatus.textContent = "录音太短，请重试";
      return;
    }
    if (durationSec < 0.4) {
      voiceStatus.textContent = "请按住说话至少 0.5 秒";
      return;
    }
    if (peak < 0.008) {
      voiceStatus.textContent = "未检测到声音，请检查麦克风权限或提高音量";
      showToast("未检测到有效音频，请靠近麦克风再试", true);
      return;
    }
    await sendVoiceTurn(wavBlob);
  } catch (err) {
    showToast(err.message, true);
    voiceStatus.textContent = "按住按钮说话，松手发送";
  }
}

transportRadios.forEach((radio) => {
  radio.addEventListener("change", (e) => {
    if (e.target.checked) {
      setTransportMode(e.target.value);
    }
  });
});

holdTalkBtn.addEventListener("mousedown", onHoldTalkStart);
holdTalkBtn.addEventListener("mouseup", onHoldTalkEnd);
holdTalkBtn.addEventListener("mouseleave", onHoldTalkEnd);
holdTalkBtn.addEventListener("touchstart", onHoldTalkStart, { passive: false });
holdTalkBtn.addEventListener("touchend", onHoldTalkEnd);
holdTalkBtn.addEventListener("touchcancel", onHoldTalkEnd);

async function sendAnswer() {
  const text = userInput.value.trim();
  if (!text || isStreaming) return;

  appendMessage("user", text);
  userInput.value = "";
  sendBtn.disabled = true;

  try {
    const result = await apiRequest(`/api/interview/${sessionId}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text }),
    });
    updateMeta(result);
    if (result.live_assessment) {
      renderLiveAssessment(result.live_assessment);
    } else {
      await refreshLive();
    }
    await refreshStatus();

    const closing =
      result.pending_action === "stream_closing" ||
      result.pending_action === "generate_report";

    if (closing) {
      appendSystem("面试即将结束...");
    }

    await consumeStream();

    if (closing || result.pending_action === "stream_closing") {
      appendSystem("正在生成评估报告...");
      await apiRequest(`/api/interview/${sessionId}/end`, { method: "POST" });
      window.location.href = reportUrl();
      return;
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (!isStreaming) sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", sendAnswer);
userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendAnswer();
  }
});

endBtn.addEventListener("click", async () => {
  endBtn.disabled = true;
  try {
    await apiRequest(`/api/interview/${sessionId}/end`, { method: "POST" });
    setNavSessionActive(false);
    window.location.href = reportUrl();
  } catch (err) {
    showToast(err.message, true);
    endBtn.disabled = false;
  }
});

document.getElementById("toggle-live").addEventListener("click", () => {
  const sidebar = document.getElementById("live-sidebar");
  const btn = document.getElementById("toggle-live");
  sidebar.classList.toggle("collapsed");
  btn.textContent = sidebar.classList.contains("collapsed") ? "展开" : "收起";
});

document.querySelectorAll(".sidebar-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const name = tab.dataset.tab;
    document.querySelectorAll(".sidebar-tab").forEach((t) => t.classList.toggle("active", t === tab));
    liveContent.classList.toggle("hidden", name !== "live");
    agendaContent.classList.toggle("hidden", name !== "agenda");
  });
});

async function init() {
  if (!sessionId) {
    showToast("缺少 session_id", true);
    return;
  }
  setTransportMode("text");
  setupInterviewNav({ status: "active", job_id: jobId ? Number(jobId) : undefined });
  await restoreMessages();
  const status = await refreshStatus();
  if (!status) {
    setupInterviewNav({ status: "active", job_id: jobId ? Number(jobId) : undefined });
  }
  const msgs = chatWindow.querySelectorAll(".message.user, .message.assistant");
  if (!msgs.length) {
    appendSystem("面试已开始，请等待面试官发言...");
    await consumeStream().catch(() => {});
  } else {
    await refreshLive();
  }
}

init();
