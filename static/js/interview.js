import { showToast, apiRequest, getQueryParam } from "/static/js/api.js";

const sessionId = getQueryParam("session_id");
const persona = getQueryParam("persona") || "tech_lead";

const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const endBtn = document.getElementById("end-btn");

let isStreaming = false;
let roundCount = 0;

const personaLabel = {
  tech_lead: "严厉的技术总监",
  hr_friendly: "亲切的 HR",
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

async function consumeStream() {
  if (!sessionId) return;
  isStreaming = true;
  sendBtn.disabled = true;

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
      resolve();
    });

    source.addEventListener("error", (event) => {
      source.close();
      isStreaming = false;
      sendBtn.disabled = false;
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
    roundCount = result.round_count;
    document.getElementById("meta-round").textContent = `轮次：${roundCount}`;

    if (result.pending_action === "stream_closing") {
      appendSystem("面试即将结束...");
    }

    await consumeStream();

    if (result.pending_action === "stream_closing") {
      appendSystem("正在生成评估报告...");
      const report = await apiRequest(`/api/interview/${sessionId}/end`, { method: "POST" });
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
    const report = await apiRequest(`/api/interview/${sessionId}/end`, {
      method: "POST",
    });
    window.location.href = `/report.html?session_id=${sessionId}`;
  } catch (err) {
    showToast(err.message, true);
    endBtn.disabled = false;
  }
});

if (!sessionId) {
  showToast("缺少 session_id", true);
} else {
  appendSystem("面试已开始，请等待面试官发言...");
  consumeStream().catch(() => {});
}
