/* ──────────────────────────────────────────────────────────────
   DailyDigest — Frontend Logic
   ────────────────────────────────────────────────────────────── */

const API_BASE = "";
let _pollTimer = null;

// ─── Init ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    setHeaderDate();
    loadGeminiKey();
    loadSources();
    checkExistingDigest();
    bindEvents();
});

function setHeaderDate() {
    const el = document.getElementById("headerDate");
    const now = new Date();
    el.textContent = now.toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
    });
}

// ─── Event Binding ───────────────────────────────────────────

function bindEvents() {
    // Sources drawer
    document.getElementById("sourcesBtn").addEventListener("click", () => toggleDrawer("sources", true));
    document.getElementById("sourcesClose").addEventListener("click", () => toggleDrawer("sources", false));
    document.getElementById("sourcesOverlay").addEventListener("click", () => toggleDrawer("sources", false));

    // Settings drawer
    document.getElementById("settingsBtn").addEventListener("click", () => toggleDrawer("settings", true));
    document.getElementById("settingsClose").addEventListener("click", () => toggleDrawer("settings", false));
    document.getElementById("settingsOverlay").addEventListener("click", () => toggleDrawer("settings", false));

    // Actions
    document.getElementById("refreshBtn").addEventListener("click", doRefresh);
    document.getElementById("addSourceBtn").addEventListener("click", addSource);
    document.getElementById("saveSettingsBtn").addEventListener("click", saveSettings);

    // Enter key on source URL field
    document.getElementById("newSourceUrl").addEventListener("keydown", (e) => {
        if (e.key === "Enter") addSource();
    });
}

// ─── Drawer Toggle ───────────────────────────────────────────

function toggleDrawer(name, open) {
    const drawer = document.getElementById(`${name}Drawer`);
    const overlay = document.getElementById(`${name}Overlay`);
    if (open) {
        drawer.classList.add("active");
        overlay.classList.add("active");
    } else {
        drawer.classList.remove("active");
        overlay.classList.remove("active");
    }
}

// ─── Settings ────────────────────────────────────────────────

function loadGeminiKey() {
    const key = localStorage.getItem("dd_gemini_key") || "";
    document.getElementById("geminiKey").value = key;
}

function saveSettings() {
    const key = document.getElementById("geminiKey").value.trim();
    localStorage.setItem("dd_gemini_key", key);
    showToast("Settings saved!", "success");
    toggleDrawer("settings", false);
}

function getGeminiKey() {
    return localStorage.getItem("dd_gemini_key") || "";
}

// ─── Sources ─────────────────────────────────────────────────

async function loadSources() {
    try {
        const resp = await fetch(`${API_BASE}/api/sources`);
        const sources = await resp.json();
        renderSourcesList(sources);
    } catch (e) {
        console.error("Failed to load sources:", e);
    }
}

function renderSourcesList(sources) {
    const container = document.getElementById("sourcesList");
    if (!sources.length) {
        container.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:1rem;">No sources configured.</p>`;
        return;
    }

    container.innerHTML = sources.map(s => `
        <div class="source-list-item" data-id="${s.id}">
            <div class="source-list-icon ${s.type === 'youtube' ? 'icon-youtube' : 'icon-website'}">
                ${s.type === 'youtube' ? '▶' : '🌐'}
            </div>
            <div class="source-list-info">
                <div class="source-list-name">${escapeHtml(s.name)}</div>
                <div class="source-list-url">${escapeHtml(s.url)}</div>
            </div>
            <button class="btn btn-danger" onclick="removeSource('${s.id}')">Remove</button>
        </div>
    `).join("");
}

async function addSource() {
    const urlInput = document.getElementById("newSourceUrl");
    const nameInput = document.getElementById("newSourceName");
    const url = urlInput.value.trim();
    const name = nameInput.value.trim();

    if (!url) {
        showToast("Please enter a URL.", "error");
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/sources`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, name }),
        });
        const data = await resp.json();

        if (!resp.ok) {
            showToast(data.error || "Failed to add source.", "error");
            return;
        }

        showToast(`Added "${data.name}"!`, "success");
        urlInput.value = "";
        nameInput.value = "";
        loadSources();
    } catch (e) {
        showToast("Network error. Is the server running?", "error");
    }
}

async function removeSource(id) {
    try {
        const resp = await fetch(`${API_BASE}/api/sources/${id}`, { method: "DELETE" });
        if (resp.ok) {
            showToast("Source removed.", "info");
            loadSources();
        } else {
            const data = await resp.json();
            showToast(data.error || "Failed to remove source.", "error");
        }
    } catch (e) {
        showToast("Network error.", "error");
    }
}

// ─── Refresh / Digest ────────────────────────────────────────

async function doRefresh() {
    const refreshBtn = document.getElementById("refreshBtn");
    refreshBtn.disabled = true;

    const geminiKey = getGeminiKey();

    try {
        const resp = await fetch(`${API_BASE}/api/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gemini_api_key: geminiKey }),
        });

        if (!resp.ok) {
            const data = await resp.json();
            showToast(data.error || "Refresh failed.", "error");
            refreshBtn.disabled = false;
            return;
        }

        showProgressBar(true);
        startPolling();
    } catch (e) {
        showToast("Network error. Is the server running?", "error");
        refreshBtn.disabled = false;
    }
}

function startPolling() {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(pollDigest, 1500);
}

async function pollDigest() {
    try {
        const resp = await fetch(`${API_BASE}/api/digest`);
        const data = await resp.json();

        updateProgress(data);

        if (data.status === "done") {
            clearInterval(_pollTimer);
            _pollTimer = null;
            setTimeout(() => showProgressBar(false), 800);
            document.getElementById("refreshBtn").disabled = false;
            renderDigest(data.digest, data.last_updated);
        } else if (data.status === "error") {
            clearInterval(_pollTimer);
            _pollTimer = null;
            showProgressBar(false);
            document.getElementById("refreshBtn").disabled = false;
            showToast(`Error: ${data.error}`, "error");
        }
    } catch (e) {
        console.error("Poll error:", e);
    }
}

async function checkExistingDigest() {
    try {
        const resp = await fetch(`${API_BASE}/api/digest`);
        const data = await resp.json();
        if (data.status === "done" && data.digest) {
            renderDigest(data.digest, data.last_updated);
        } else if (data.status === "fetching" || data.status === "summarizing") {
            showProgressBar(true);
            startPolling();
            document.getElementById("refreshBtn").disabled = true;
        }
    } catch (e) {
        // Server not ready yet, fine
    }
}

// ─── Progress Bar ────────────────────────────────────────────

function showProgressBar(show) {
    const container = document.getElementById("progressContainer");
    const bar = document.getElementById("progressBar");
    if (show) {
        container.classList.add("active");
        bar.classList.add("indeterminate");
    } else {
        bar.classList.remove("indeterminate");
        bar.style.width = "100%";
        setTimeout(() => {
            container.classList.remove("active");
            bar.style.width = "0%";
        }, 500);
    }
}

function updateProgress(data) {
    document.getElementById("progressText").textContent = data.progress || "";
    document.getElementById("progressDetail").textContent = data.progress_detail || "";
}

// ─── Render Digest ───────────────────────────────────────────

function renderDigest(digest, lastUpdated) {
    // Hide welcome card
    document.getElementById("welcomeCard").style.display = "none";

    // Show top headlines
    if (digest.top_headlines) {
        const banner = document.getElementById("headlinesBanner");
        banner.style.display = "block";
        document.getElementById("headlinesContent").innerHTML = formatSummary(digest.top_headlines);
    }

    // Render source cards
    const grid = document.getElementById("digestGrid");
    grid.innerHTML = "";

    const sources = digest.sources || [];
    sources.forEach((source, i) => {
        const card = createSourceCard(source, i);
        grid.appendChild(card);
    });

    // Last updated line
    let updatedEl = document.querySelector(".last-updated");
    if (!updatedEl) {
        updatedEl = document.createElement("div");
        updatedEl.className = "last-updated";
        document.getElementById("mainContent").appendChild(updatedEl);
    }
    if (lastUpdated) {
        const d = new Date(lastUpdated);
        updatedEl.textContent = `Last updated: ${d.toLocaleString()}`;
    }
}

function createSourceCard(source, index) {
    const card = document.createElement("div");
    card.className = "source-card";
    card.style.animationDelay = `${index * 0.05}s`;

    const isYouTube = source.type === "youtube";
    const items = isYouTube ? (source.videos || []) : (source.articles || []);
    const itemLabel = isYouTube ? "videos" : "articles";
    const badgeClass = isYouTube ? "badge-youtube" : "badge-website";
    const badgeText = isYouTube ? "YouTube" : "Website";
    const badgeIcon = isYouTube ? "▶" : "🌐";

    card.innerHTML = `
        <div class="source-card-header">
            <span class="source-type-badge ${badgeClass}">${badgeIcon} ${badgeText}</span>
            <span class="source-card-name">${escapeHtml(source.name)}</span>
            <a href="${escapeHtml(source.url)}" target="_blank" class="source-card-link" title="Visit source">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
        </div>
        <div class="source-card-body">
            <div class="source-summary">${formatSummary(source.summary || "No summary available.")}</div>
        </div>
        ${items.length ? `
            <div class="source-card-footer">
                <button class="toggle-articles" onclick="toggleArticles(this)">
                    Show ${items.length} ${itemLabel} ▾
                </button>
                <ul class="article-list" style="display:none;">
                    ${items.map(item => `
                        <li class="article-item">
                            <a href="${escapeHtml(item.url)}" target="_blank" class="article-title">${escapeHtml(item.title)}</a>
                            <div class="article-meta">${formatDate(item.published)}</div>
                        </li>
                    `).join("")}
                </ul>
            </div>
        ` : ""}
    `;

    return card;
}

function toggleArticles(btn) {
    const list = btn.nextElementSibling;
    const isHidden = list.style.display === "none";
    list.style.display = isHidden ? "block" : "none";
    btn.textContent = isHidden
        ? btn.textContent.replace("Show", "Hide").replace("▾", "▴")
        : btn.textContent.replace("Hide", "Show").replace("▴", "▾");
}

// ─── Helpers ─────────────────────────────────────────────────

function formatSummary(text) {
    // Convert bullet points and numbered lists to HTML
    return text
        .split("\n")
        .map(line => {
            line = line.trim();
            if (!line) return "";
            if (line.startsWith("•") || line.startsWith("-") || line.startsWith("*")) {
                return `<p style="padding-left:1em;text-indent:-1em;">${escapeHtml(line)}</p>`;
            }
            if (/^\d+\./.test(line)) {
                return `<p style="padding-left:1.5em;text-indent:-1.5em;">${escapeHtml(line)}</p>`;
            }
            return `<p>${escapeHtml(line)}</p>`;
        })
        .join("");
}

function formatDate(isoStr) {
    if (!isoStr) return "";
    try {
        const d = new Date(isoStr);
        const now = new Date();
        const diffMs = now - d;
        const diffH = Math.floor(diffMs / (1000 * 60 * 60));

        if (diffH < 1) return "Just now";
        if (diffH < 24) return `${diffH}h ago`;
        if (diffH < 48) return "Yesterday";
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
        return "";
    }
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
