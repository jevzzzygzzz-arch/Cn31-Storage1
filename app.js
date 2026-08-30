// Educational Cybersecurity measures purposes: sanitized for safe sharing, review, and classroom-style inspection of the code here.
const icons = {
  shield: '<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4.8-2.9 8.2-7 10-4.1-1.8-7-5.2-7-10V6l7-3Z"/><path d="m9 12 2 2 4-5"/></svg>',
  network: '<svg viewBox="0 0 24 24"><path d="M12 3v5M5 8l4 3M19 8l-4 3M5 17l4-3M19 17l-4-3M12 16v5"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="3" r="1.5"/><circle cx="5" cy="8" r="1.5"/><circle cx="19" cy="8" r="1.5"/><circle cx="5" cy="17" r="1.5"/><circle cx="19" cy="17" r="1.5"/><circle cx="12" cy="21" r="1.5"/></svg>',
  layers: '<svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m4 12 8 4.5 8-4.5M4 16l8 4.5 8-4.5"/></svg>',
  refresh: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v6h-6"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 14h10l1-14"/><path d="M9 7V4h6v3"/></svg>',
  inbox: '<svg viewBox="0 0 24 24"><path d="M4 13 7 5h10l3 8"/><path d="M4 13h5l2 3h2l2-3h5v6H4v-6Z"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M21 3 10 14"/><path d="m21 3-7 18-4-7-7-4 18-7Z"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v5l3 2"/></svg>'
};

function setText(id, value) {
  const node = document.getElementById(id);
  if (!node) return;
  if (node.textContent !== value) {
    node.textContent = value;
    node.classList.remove("bump");
    void node.offsetWidth;
    node.classList.add("bump");
  }
}

function formatUptime(seconds) {
  const safe = Number(seconds || 0);
  const minutes = Math.floor(safe / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${Math.floor(safe % 60)}s`;
  return `${Math.floor(safe)}s`;
}

function renderTokens(tokens) {
  const list = document.getElementById("tokenList");
  if (!list) return;
  if (!tokens || tokens.length === 0) {
    list.innerHTML = '<div class="empty">No tokens in queue</div>';
    return;
  }
  list.replaceChildren(...tokens.slice(0, 24).map((item, index) => {
    const token = item.token || "token";
    const age = item.age ?? item.age_seconds ?? 0;
    const row = document.createElement("div");
    const tokenText = document.createElement("span");
    const tokenMeta = document.createElement("span");
    row.className = "token-row";
    row.style.animationDelay = `${Math.min(index, 12) * 55}ms`;
    tokenText.className = "token-text";
    tokenMeta.className = "token-meta";
    tokenText.textContent = token;
    tokenMeta.textContent = `${age}s`;
    row.append(tokenText, tokenMeta);
    return row;
  }));
}

function setState(label, text, kind = "live") {
  if (!label) return;
  label.textContent = text;
  label.classList.toggle("is-offline", kind === "offline");
  label.classList.toggle("is-error", kind === "error");
}

async function refreshDashboard() {
  const label = document.getElementById("stateLabel");
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error("status failed");
    const data = await response.json();
    const peak = Math.max(data.peak_queue || 0, data.queue_size || 0, 1);
    const fill = Math.min(100, Math.round(((data.queue_size || 0) / peak) * 100));
    setText("queueSize", String(data.queue_size || 0));
    setText("received", String(data.total_received || 0));
    setText("served", String(data.total_served || 0));
    setText("expired", String(data.total_expired || 0));
    setText("peakQueue", String(data.peak_queue || 0));
    setText("rate", Number(data.tokens_per_minute || 0).toFixed(2));
    setText("ttl", `${data.token_ttl_seconds || 0}s`);
    setText("uptime", formatUptime(data.uptime_seconds));
    const meter = document.getElementById("queueMeter");
    if (meter) meter.style.width = `${fill}%`;
    renderTokens(data.recent_tokens || []);
    setState(label, "Live");
  } catch {
    setState(label, "Offline", "offline");
  }
}

async function flushQueue() {
  const label = document.getElementById("stateLabel");
  const button = document.getElementById("flushButton");
  try {
    if (button) {
      button.disabled = true;
      button.querySelector("span:last-child").textContent = "Flushing...";
    }
    const response = await fetch("/api/tokens", { method: "DELETE" });
    if (!response.ok) throw new Error("flush failed");
    setState(label, "Flushed");
    await refreshDashboard();
  } catch {
    setState(label, "Flush failed", "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.querySelector("span:last-child").textContent = "Flush";
    }
  }
}

document.querySelectorAll("[data-icon]").forEach((node) => {
  node.innerHTML = icons[node.dataset.icon] || "";
});

document.querySelectorAll(".stat-card, .panel, .hero-panel").forEach((node, index) => {
  node.style.animationDelay = `${index * 55}ms`;
});

document.getElementById("refreshButton")?.addEventListener("click", refreshDashboard);
document.getElementById("flushButton")?.addEventListener("click", flushQueue);
refreshDashboard();
window.setInterval(refreshDashboard, 3000);
