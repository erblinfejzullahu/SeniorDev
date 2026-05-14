// admin.js — Bella Vista Admin Dashboard
// API_BASE is loaded from config.js

const TOTAL_TABLES = 5;

const OPENING_HOURS = {
  0: null,
  1: { open: 12, close: 22 },
  2: { open: 12, close: 22 },
  3: { open: 12, close: 22 },
  4: { open: 12, close: 23 },
  5: { open: 11, close: 23 },
  6: { open: 11, close: 21 },
};

let allReservations = [];
let allCallbacks    = [];
let calendarDate    = new Date();
let toastTimer      = null;

// ── AUTH HELPERS ──────────────────────────────────────────────────
function getToken() {
  return sessionStorage.getItem("admin_token") || "";
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + getToken()
  };
}

function handleUnauthorized() {
  sessionStorage.removeItem("admin_token");
  document.getElementById("dashboard").classList.remove("visible");
  document.getElementById("login-overlay").style.display = "flex";
  showToast("Session expired. Please log in again.");
}

// ── INIT ──────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  document.getElementById("page-date").textContent =
    new Date().toLocaleDateString("en-GB", { weekday:"long", day:"numeric", month:"long", year:"numeric" });
  document.getElementById("filter-date").value = todayStr();

  if (getToken()) showDashboard();
});

// ── LOGIN ─────────────────────────────────────────────────────────
document.getElementById("login-btn").addEventListener("click", attemptLogin);
document.getElementById("password-input").addEventListener("keydown", e => {
  if (e.key === "Enter") attemptLogin();
});

async function attemptLogin() {
  const password = document.getElementById("password-input").value;
  const loginBtn = document.getElementById("login-btn");
  loginBtn.disabled = true;
  loginBtn.textContent = "Verifying...";

  try {
    const res = await fetch(API_BASE + "/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password })
    });

    if (!res.ok) {
      document.getElementById("login-error").classList.add("visible");
      document.getElementById("password-input").value = "";
      document.getElementById("password-input").focus();
      return;
    }

    const data = await res.json();
    sessionStorage.setItem("admin_token", data.token);
    document.getElementById("login-error").classList.remove("visible");
    showDashboard();
  } catch {
    showToast("Could not reach server. Is the backend running?");
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = "Enter";
  }
}

function showDashboard() {
  document.getElementById("login-overlay").style.display = "none";
  document.getElementById("dashboard").classList.add("visible");
  loadAllData();
}

async function doLogout() {
  try {
    await fetch(API_BASE + "/admin/logout", { method: "POST", headers: authHeaders() });
  } catch (_) {}
  sessionStorage.removeItem("admin_token");
  document.getElementById("dashboard").classList.remove("visible");
  document.getElementById("login-overlay").style.display = "flex";
  document.getElementById("password-input").value = "";
}

document.getElementById("logout-btn").addEventListener("click", doLogout);
document.getElementById("mobile-logout-btn").addEventListener("click", doLogout);

// ── CHANGE PASSWORD ───────────────────────────────────────────────
document.getElementById("change-password-btn").addEventListener("click", () => {
  document.getElementById("cp-current").value = "";
  document.getElementById("cp-new").value     = "";
  document.getElementById("cp-confirm").value = "";
  document.getElementById("cp-error").textContent = "";
  document.getElementById("cp-modal").classList.add("visible");
});

document.getElementById("cp-cancel").addEventListener("click", () => {
  document.getElementById("cp-modal").classList.remove("visible");
});

document.getElementById("cp-modal").addEventListener("click", (e) => {
  if (e.target === document.getElementById("cp-modal")) {
    document.getElementById("cp-modal").classList.remove("visible");
  }
});

document.getElementById("cp-submit").addEventListener("click", async () => {
  const current = document.getElementById("cp-current").value;
  const next    = document.getElementById("cp-new").value;
  const confirm = document.getElementById("cp-confirm").value;
  const errEl   = document.getElementById("cp-error");
  const submitBtn = document.getElementById("cp-submit");

  errEl.textContent = "";

  if (!current || !next || !confirm) {
    errEl.textContent = "All fields are required."; return;
  }
  if (next.length < 6) {
    errEl.textContent = "New password must be at least 6 characters."; return;
  }
  if (next !== confirm) {
    errEl.textContent = "New passwords do not match."; return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Saving...";

  try {
    const res = await fetch(API_BASE + "/admin/change-password", {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ current_password: current, new_password: next })
    });

    const data = await res.json();

    if (!res.ok) {
      errEl.textContent = data.detail || "Failed to update password.";
      return;
    }

    // Password changed — all tokens are now invalid, force re-login
    document.getElementById("cp-modal").classList.remove("visible");
    showToast("Password updated! Please log in again.");
    setTimeout(doLogout, 1500);

  } catch {
    errEl.textContent = "Server error. Please try again.";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Update Password";
  }
});

// ── NAV ───────────────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    const titles = { overview:"Overview", reservations:"Reservations", callbacks:"Callback Requests" };
    document.getElementById("page-title").textContent = titles[btn.dataset.tab];
  });
});

document.getElementById("refresh-btn").addEventListener("click", loadAllData);

// ── DATA ──────────────────────────────────────────────────────────
async function loadAllData() {
  await Promise.all([loadReservations(), loadCallbacks()]);
  renderOverview();
}

async function loadReservations() {
  try {
    const res = await fetch(API_BASE + "/admin/reservations", { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    const data = await res.json();
    allReservations = data.reservations || [];
    renderReservations(allReservations);
  } catch { showToast("Could not load reservations"); }
}

async function loadCallbacks() {
  try {
    const res = await fetch(API_BASE + "/admin/callbacks", { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    const data = await res.json();
    allCallbacks = data.callbacks || [];
    renderCallbacks(allCallbacks);
  } catch { showToast("Could not load callbacks"); }
}

// ── OVERVIEW ──────────────────────────────────────────────────────
function renderOverview() {
  const today   = todayStr();
  const nowHour = new Date().getHours();

  const todayRes    = allReservations.filter(r => r.date === today);
  const todayGuests = todayRes.reduce((s, r) => s + (r.party_size || 0), 0);
  const pendingCbs  = allCallbacks.filter(c => c.status === "pending").length;
  const usedNow     = tablesUsedInSlot(today, pad(nowHour) + ":00");
  const freeNow     = Math.max(0, TOTAL_TABLES - usedNow);

  document.getElementById("stat-today-guests").textContent       = todayGuests;
  document.getElementById("stat-today-reservations").textContent = todayRes.length;
  document.getElementById("stat-tables-free").textContent        = freeNow;
  document.getElementById("stat-pending-callbacks").textContent  = pendingCbs;

  renderCalendar();
}

// ── CALENDAR ──────────────────────────────────────────────────────
function renderCalendar() {
  const container  = document.getElementById("calendar-container");
  const today      = todayStr();
  const year       = calendarDate.getFullYear();
  const month      = calendarDate.getMonth();
  const monthLabel = calendarDate.toLocaleDateString("en-GB", { month:"long", year:"numeric" });
  const firstDay   = new Date(year, month, 1);
  const lastDay    = new Date(year, month + 1, 0);

  let startOffset = firstDay.getDay() - 1;
  if (startOffset < 0) startOffset = 6;

  let html = `
    <div class="cal-wrapper">
      <div class="cal-nav">
        <button class="cal-btn" id="cal-prev">&#8249;</button>
        <span class="cal-title">${monthLabel}</span>
        <button class="cal-btn" id="cal-next">&#8250;</button>
      </div>
      <div class="cal-labels">
        <span>Mon</span><span>Tue</span><span>Wed</span>
        <span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
      </div>
      <div class="cal-grid">
  `;

  for (let i = 0; i < startOffset; i++) html += `<div class="cal-cell cal-empty"></div>`;

  for (let d = 1; d <= lastDay.getDate(); d++) {
    const mm      = pad(month + 1);
    const dd      = pad(d);
    const dateStr = `${year}-${mm}-${dd}`;
    const dow     = new Date(year, month, d).getDay();
    const dowIdx  = dow === 0 ? 6 : dow - 1;
    const closed  = OPENING_HOURS[dowIdx] === null;
    const isToday = dateStr === today;
    const isPast  = dateStr < today;
    const dayRes  = allReservations.filter(r => r.date === dateStr);
    const guests  = dayRes.reduce((s, r) => s + (r.party_size || 0), 0);
    const hasRes  = dayRes.length > 0 && !closed;

    let cls = "cal-cell";
    if (isToday) cls += " cal-today";
    if (isPast)  cls += " cal-past";
    if (closed)  cls += " cal-closed";
    if (hasRes)  cls += " cal-has-res";

    let inner = `<div class="cal-num">${d}</div>`;
    if (closed)      inner += `<div class="cal-tag closed-tag">Closed</div>`;
    else if (hasRes) inner += `<div class="cal-tag res-tag">${dayRes.length} res · ${guests} guests</div>`;

    html += `<div class="${cls}" data-date="${dateStr}">${inner}</div>`;
  }

  html += `</div></div>`;
  container.innerHTML = html;

  document.getElementById("cal-prev").addEventListener("click", () => {
    calendarDate = new Date(year, month - 1, 1); renderCalendar();
  });
  document.getElementById("cal-next").addEventListener("click", () => {
    calendarDate = new Date(year, month + 1, 1); renderCalendar();
  });

  container.querySelectorAll(".cal-cell[data-date]").forEach(cell => {
    cell.addEventListener("click", () => {
      const date = cell.dataset.date;
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
      document.querySelector('[data-tab="reservations"]').classList.add("active");
      document.getElementById("tab-reservations").classList.add("active");
      document.getElementById("page-title").textContent = "Reservations";
      document.getElementById("filter-date").value = date;
      renderReservations(allReservations.filter(r => r.date === date));
      showToast("Showing: " + formatDate(date));
    });
  });
}

// ── AVAILABILITY HELPER ───────────────────────────────────────────
function tablesUsedInSlot(date, time) {
  let total = 0;
  const slotStart = new Date(`${date}T${time}:00`);
  const slotEnd   = new Date(slotStart.getTime() + 3600000);
  for (const r of allReservations) {
    const t = (r.time || "").slice(0, 5);
    if (!r.date || !t) continue;
    const rs = new Date(`${r.date}T${t}:00`);
    const re = new Date(rs.getTime() + 3600000);
    if (rs < slotEnd && re > slotStart) total += (r.tables_needed || 1);
  }
  return total;
}

// ── RESERVATIONS ──────────────────────────────────────────────────
function renderReservations(data) {
  const tbody = document.getElementById("reservations-body");
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading">No reservations found.</td></tr>';
    return;
  }
  const today   = todayStr();
  const nowTime = new Date().toTimeString().slice(0, 5);
  tbody.innerHTML = data.map(r => {
    const past  = r.date < today || (r.date === today && (r.time || "").slice(0, 5) < nowTime);
    const badge = past
      ? '<span class="badge past">Past</span>'
      : '<span class="badge upcoming">Upcoming</span>';
    return `<tr>
      <td class="td-name">${r.name}</td>
      <td>${r.phone || "—"}</td>
      <td>${formatDate(r.date)}</td>
      <td>${formatTime((r.time || "").slice(0, 5))}</td>
      <td>${r.party_size}</td>
      <td>${r.tables_needed || "—"}</td>
      <td class="td-small">${r.created_at ? formatDateTime(r.created_at) : "—"}</td>
      <td>${badge} <button class="action-btn delete-btn" onclick="deleteRes('${r.id}')">Delete</button></td>
    </tr>`;
  }).join("");
}

document.getElementById("filter-btn").addEventListener("click", () => {
  const d = document.getElementById("filter-date").value;
  if (d) renderReservations(allReservations.filter(r => r.date === d));
});

document.getElementById("clear-filter-btn").addEventListener("click", () => {
  document.getElementById("filter-date").value = "";
  renderReservations(allReservations);
});

async function deleteRes(id) {
  if (!confirm("Delete this reservation?")) return;
  try {
    const res = await fetch(`${API_BASE}/admin/reservations/${id}`, {
      method: "DELETE", headers: authHeaders()
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    allReservations = allReservations.filter(r => r.id !== id);
    renderReservations(allReservations);
    renderOverview();
    showToast("Reservation deleted");
  } catch { showToast("Failed to delete"); }
}

// ── CALLBACKS ─────────────────────────────────────────────────────
function renderCallbacks(data) {
  const tbody   = document.getElementById("callbacks-body");
  const pending = document.getElementById("show-pending-only").checked;
  const list    = pending ? data.filter(c => c.status === "pending") : data;
  if (!list || list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading">${pending ? "No pending callbacks." : "No callbacks."}</td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(c => {
    const badge = c.status === "done"
      ? '<span class="badge done">Done</span>'
      : '<span class="badge pending">Pending</span>';
    const btn = c.status === "pending"
      ? `<button class="action-btn done-btn" onclick="markDone('${c.id}')">Mark Done</button>`
      : `<button class="action-btn" disabled>Done</button>`;
    return `<tr>
      <td class="td-name">${c.name}</td>
      <td>${c.phone}</td>
      <td class="td-small">${c.created_at ? formatDateTime(c.created_at) : "—"}</td>
      <td>${badge}</td>
      <td>${btn}</td>
    </tr>`;
  }).join("");
}

document.getElementById("show-pending-only").addEventListener("change", () => renderCallbacks(allCallbacks));

async function markDone(id) {
  try {
    const res = await fetch(`${API_BASE}/admin/callbacks/${id}/done`, {
      method: "PATCH", headers: authHeaders()
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    const c = allCallbacks.find(c => c.id === id);
    if (c) c.status = "done";
    renderCallbacks(allCallbacks);
    renderOverview();
    showToast("Marked as done");
  } catch { showToast("Failed to update"); }
}

// ── HELPERS ───────────────────────────────────────────────────────
function todayStr() { return new Date().toISOString().split("T")[0]; }
function pad(n)     { return String(n).padStart(2, "0"); }

function formatDate(s) {
  if (!s) return "—";
  return new Date(s + "T12:00:00").toLocaleDateString("en-GB",
    { weekday:"short", day:"numeric", month:"short", year:"numeric" });
}

function formatTime(s) {
  if (!s) return "—";
  const [h, m] = s.split(":");
  const hr = parseInt(h);
  return `${hr % 12 || 12}:${m} ${hr >= 12 ? "PM" : "AM"}`;
}

function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day:"numeric", month:"short" })
       + " " + d.toLocaleTimeString("en-GB", { hour:"2-digit", minute:"2-digit" });
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3000);
}
