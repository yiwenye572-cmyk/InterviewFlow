import { showToast, apiRequest, getQueryParam } from "/static/js/api.js";

const sessionId = getQueryParam("session_id");
const persona = getQueryParam("persona") || "tech_lead";

const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const endBtn = document.getElementById("end-btn");
const typingIndicator = document.getElementById("typing-indicator");
const liveContent = document.getElementById("live-content");

let isStreaming = false;
let roundCount = 0;

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

document.getElementById("meta-persona").textContent =
  `面试官：${personaLabel[persona] || persona}`;

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

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function updateMeta(status) {
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
  if (!sessionId) return;
  try {
    const status = await apiRequest(`/api/interview/${sessionId}/status`);
    updateMeta(status);
  } catch {
    /* ignore */
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
  if (!sessionId) return;
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
      window.location.href = `/report.html?session_id=${sessionId}`;
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
    window.location.href = `/report.html?session_id=${sessionId}`;
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

async function init() {
  if (!sessionId) {
    showToast("缺少 session_id", true);
    return;
  }
  await restoreMessages();
  await refreshStatus();
  const msgs = chatWindow.querySelectorAll(".message.user, .message.assistant");
  if (!msgs.length) {
    appendSystem("面试已开始，请等待面试官发言...");
    await consumeStream().catch(() => {});
  } else {
    await refreshLive();
  }
}

init();
