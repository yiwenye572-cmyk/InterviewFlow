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

export { showToast, apiRequest, getQueryParam, scoreClass, recommendationClass };
