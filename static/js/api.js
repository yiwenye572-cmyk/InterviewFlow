function showToast(message, isError = false) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), 3500);
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }
  if (!response.ok) {
    const detail = data?.detail || (typeof data === "string" ? data : "Request failed");
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function scoreClass(score) {
  if (score >= 75) return "score-high";
  if (score >= 60) return "score-mid";
  return "score-low";
}

function recommendationClass(rec) {
  const map = { hire: "hire", hold: "hold", reject: "reject" };
  return map[rec] || "hold";
}

const recommendationLabel = {
  hire: "推荐录用",
  hold: "待定",
  reject: "不推荐",
};

function formatRecommendation(rec) {
  return recommendationLabel[rec] || rec;
}

const answerQualityLabel = {
  strong: "优秀",
  adequate: "合格",
  weak: "薄弱",
};

function formatAnswerQuality(quality) {
  if (!quality) return "";
  return answerQualityLabel[quality] || quality;
}

const timelineDimensionLabel = {
  partial_score: "本轮得分",
  calibration: "校准说明",
  communication: "沟通能力",
  job_fit: "岗位匹配",
  live_aggregate: "综合预估",
  security: "安全拦截",
};

function formatTimelineDimension(dim) {
  return timelineDimensionLabel[dim] || dim;
}

const legacyRiskPrefixes = [
  [/^Resume mismatch:\s*/i, "简历不一致："],
  [/^Off-topic answer:\s*/i, "答非所问："],
  [/^Weak answer:\s*/i, "回答薄弱："],
  [/^Poor communication:\s*/i, "沟通欠佳："],
];

function formatLiveAssessmentText(text) {
  if (!text) return text;
  for (const [pattern, prefix] of legacyRiskPrefixes) {
    if (pattern.test(text)) {
      return text.replace(pattern, prefix);
    }
  }
  return text;
}

const legacyTimelineReasonExact = {
  "Calibrator adjusted partial score": "校准器调整了本轮得分",
  "Weak answer quality": "回答质量薄弱",
  "Low evidence density — job fit capped by rule": "证据不足，岗位匹配分按规则封顶",
  "Off-topic or adversarial input": "答非所问或对抗性输入",
  "Weighted live score updated from recent rounds": "近期轮次加权更新综合预估分",
  "Security guard blocked adversarial input": "安全策略拦截了对抗性输入",
  "Rule-based fallback calibration": "基于规则的校准兜底",
};

function formatTimelineReason(reason) {
  if (!reason) return reason;
  if (legacyTimelineReasonExact[reason]) {
    return legacyTimelineReasonExact[reason];
  }
  if (/^Communication signal:\s*vague/i.test(reason)) {
    return "沟通信号：含糊";
  }
  if (/^Communication signal:\s*evasive/i.test(reason)) {
    return "沟通信号：回避";
  }
  return formatLiveAssessmentText(reason);
}

export {
  showToast,
  apiRequest,
  getQueryParam,
  scoreClass,
  recommendationClass,
  formatRecommendation,
  formatAnswerQuality,
  formatTimelineDimension,
  formatTimelineReason,
  formatLiveAssessmentText,
};
