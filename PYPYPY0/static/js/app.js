const state = { page: "dashboard", snapshot: null, macroRefreshNeeded: true };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function request(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const data = await response.json();
    if (!response.ok || data.success === false) throw new Error(data.error || data.message || "Aksi tidak dapat dijalankan pada status ini.");
    return data;
  } catch (error) {
    showNotice(error.message, true);
    throw error;
  }
}

function showNotice(message, isError = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = !message;
  clearTimeout(showNotice.timer);
  showNotice.timer = setTimeout(() => { notice.hidden = true; }, isError ? 6500 : 3000);
}

function seconds(value) { return `${Number(value || 0).toFixed(2)}s`; }

function renderStatus(snapshot) {
  state.snapshot = snapshot;
  $("#stateLabel").textContent = snapshot.state;
  $("#statePill").dataset.state = snapshot.state;
  $("#statusMessage").textContent = snapshot.message || "Siap digunakan";
  $("#eventCount").textContent = snapshot.event_count || 0;
  $("#duration").textContent = seconds(snapshot.duration);
  $("#mousePosition").textContent = snapshot.mouse_position ? `${snapshot.mouse_position[0]}, ${snapshot.mouse_position[1]}` : "—";
  $("#activeMacro").textContent = snapshot.loaded_macro || "Belum ada";
  $("#recorderState").textContent = snapshot.state.includes("RECORDING") ? snapshot.state.replace("_", " ") : "IDLE";
  $("#autoclickerState").textContent = snapshot.autoclicker_active ? "ACTIVE" : "OFF";
  $("#clickCountStatus").textContent = `${snapshot.autoclicker_clicks || 0} klik dilakukan`;
  $("#recordPauseBtn").innerHTML = snapshot.state === "PAUSED_RECORDING" ? "<i class=\"bi bi-play-fill\"></i> Resume" : "<i class=\"bi bi-pause-fill\"></i> Jeda";
  const hotkeys = snapshot.hotkeys || {};
  $("#hotkeys").innerHTML = Object.entries(hotkeys).map(([name, key]) => `<span class="key">${key}: ${name.replace("_", " ")}</span>`).join("");
  if (snapshot.hotkey_error) showNotice(snapshot.hotkey_error, true);
}

async function updateStatus() {
  try {
    const response = await fetch("/api/status");
    const snapshot = await response.json();
    renderStatus(snapshot);
    if (state.page === "recorder" && (snapshot.state === "RECORDING" || snapshot.event_count !== state.lastEventCount)) await loadEvents();
    state.lastEventCount = snapshot.event_count;
    if (state.page === "macros" && state.macroRefreshNeeded) await loadMacros();
  } catch { /* connection status is retried on the next poll */ }
}

async function perform(url, body) {
  const data = await request(url, { method: "POST", body });
  renderStatus(data);
  state.macroRefreshNeeded = true;
  return data;
}

async function loadEvents() {
  const response = await fetch("/api/events?limit=150");
  const data = await response.json();
  const events = data.events || [];
  $("#events").textContent = events.length ? events.map(event => JSON.stringify(event)).join("\n") : "Belum ada event";
}

function escapeHTML(text) {
  return String(text).replace(/[&<>'"]/g, character => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#039;", '"':"&quot;" }[character]));
}

async function loadMacros() {
  const response = await fetch("/api/macros");
  const data = await response.json();
  const macros = data.macros || [];
  $("#macroList").innerHTML = macros.length ? macros.map(macro => `
    <article class="card macro-row"><div class="macro-icon"><i class="bi bi-file-earmark-play"></i></div><div class="macro-details"><div class="macro-name">${escapeHTML(macro.name)}</div><div class="macro-meta">${macro.invalid ? "File tidak valid" : `${macro.event_count} event · ${seconds(macro.duration)}`}</div></div><div class="macro-actions"><button class="btn secondary small-btn" data-load="${escapeHTML(macro.name)}" ${macro.invalid ? "disabled" : ""}>Load</button><button class="btn danger small-btn" data-delete="${escapeHTML(macro.name)}">Hapus</button></div></article>`).join("") : "<div class=\"empty-state\">Belum ada macro tersimpan. Rekam aksi lalu simpan dari halaman ini.</div>";
  state.macroRefreshNeeded = false;
}

function setPage(page) {
  state.page = page;
  $$(".page").forEach(element => element.classList.toggle("active", element.id === page));
  $$(".nav-link").forEach(element => element.classList.toggle("active", element.dataset.page === page));
  const labels = { dashboard:["OVERVIEW","Dashboard"], recorder:["CAPTURE INPUT","Recorder"], autoclicker:["REPEATED CLICKS","Autoclicker"], macros:["LIBRARY","Macros"], settings:["PREFERENCES","Settings"] };
  $("#pageEyebrow").textContent = labels[page][0]; $("#pageTitle").textContent = labels[page][1];
  if (page === "recorder") loadEvents();
  if (page === "macros") { state.macroRefreshNeeded = true; loadMacros(); }
}

document.addEventListener("DOMContentLoaded", () => {
  $$(".nav-link").forEach(button => button.addEventListener("click", () => setPage(button.dataset.page)));
  $("#recordBtn").addEventListener("click", () => perform("/api/record"));
  $("#quickRecord").addEventListener("click", () => perform("/api/record"));
  $("#recordStopBtn").addEventListener("click", () => perform("/api/stop"));
  $("#quickStop").addEventListener("click", () => perform("/api/stop"));
  $("#quickPlay").addEventListener("click", () => perform("/api/play", { speed: Number($("#speed").value), loop: Number($("#loop").value) }));
  $("#recordPauseBtn").addEventListener("click", () => perform(state.snapshot?.state === "PAUSED_RECORDING" ? "/api/record/resume" : "/api/record/pause"));
  $("#refreshEvents").addEventListener("click", loadEvents);
  $("#autoclickStart").addEventListener("click", () => perform("/api/autoclicker/start", { interval: Number($("#clickInterval").value) / 1000, count: Number($("#clickCount").value), button: $("#clickButton").value, jitter: Number($("#clickJitter").value) / 1000 }));
  $("#autoclickStop").addEventListener("click", () => perform("/api/autoclicker/stop"));
  $("#saveBtn").addEventListener("click", async () => { const filename = window.prompt("Nama macro:", state.snapshot?.loaded_macro || "macro-baru"); if (filename?.trim()) { await perform("/api/save", { filename: filename.trim() }); await loadMacros(); showNotice("Macro berhasil disimpan."); } });
  $("#macroList").addEventListener("click", async (event) => { const load = event.target.closest("[data-load]")?.dataset.load; const remove = event.target.closest("[data-delete]")?.dataset.delete; if (load) { await perform("/api/load", { filename: load }); showNotice(`Macro '${load}' dimuat.`); } if (remove && window.confirm(`Hapus macro '${remove}'?`)) { await request(`/api/macros/${encodeURIComponent(remove)}`, { method:"DELETE" }); await loadMacros(); showNotice("Macro dihapus."); } });
  const savePlaybackSettings = () => perform("/api/playback-settings", { speed: Number($("#speed").value), loop: Number($("#loop").value) });
  $("#speed").addEventListener("input", event => { $("#speedValue").textContent = `${Number(event.target.value).toFixed(2)}×`; savePlaybackSettings().catch(() => {}); });
  $("#loop").addEventListener("change", () => savePlaybackSettings().catch(() => {}));
  updateStatus();
  setInterval(updateStatus, 750);
});
