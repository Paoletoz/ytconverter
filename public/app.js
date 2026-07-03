const API_BASE = "https://ytconverter-backend.onrender.com";

const form = document.getElementById("form");
const urlInput = document.getElementById("url");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const thumbEl = document.getElementById("thumb");
const titleEl = document.getElementById("title");
const metaEl = document.getElementById("meta");

let currentUrl = "";

function formatDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  currentUrl = url;
  resultEl.classList.add("hidden");
  setStatus("Analisi in corso...");
  analyzeBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/info?url=${encodeURIComponent(url)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Errore sconosciuto");

    thumbEl.src = data.thumbnail || "";
    titleEl.textContent = data.title || "";
    metaEl.textContent = [data.uploader, formatDuration(data.duration)]
      .filter(Boolean)
      .join(" · ");

    resultEl.classList.remove("hidden");
    setStatus("");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    analyzeBtn.disabled = false;
  }
});

document.querySelectorAll(".quality").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!currentUrl) return;
    const quality = btn.dataset.quality;
    setStatus("Avvio del download... può richiedere qualche secondo.");
    const link = document.createElement("a");
    link.href = `${API_BASE}/api/download?url=${encodeURIComponent(currentUrl)}&quality=${quality}`;
    link.click();
  });
});
