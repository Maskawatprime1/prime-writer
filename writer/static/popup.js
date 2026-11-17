"use strict";
const $ = (s) => document.querySelector(s);
const src = $("#src");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MODE_LABELS = { fix: "Fix grammar", standard: "Standard", fluent: "Fluent", formal: "Formal", concise: "Concise", casual: "Casual", academic: "Academic", simple: "Simple" };

let issues = [], tab = "check", mode = "standard", paraText = "", seq = 0, editTimer = null;
const desk = () => window.pywebview && window.pywebview.api;
const pref = (k) => { try { return localStorage.getItem("lw" + k) || null; } catch { return null; } };

async function api(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

/* Called from Python each time the hotkey fires. */
window.openWith = (p) => {
  seq++;
  $("#appname").textContent = (p.exe || "this app").replace(/\.exe$/i, "");
  $("#off-here").hidden = !p.exe;
  src.value = p.text || "";
  issues = []; paraText = ""; renderIssues();
  $("#para-out").className = "para-out muted"; $("#para-out").textContent = "Pick a mode.";
  const note = $("#note");
  note.hidden = !!p.hadSelection;
  note.textContent = "No text was selected. Type here; Replace will insert it at the cursor in the app.";
  if (p.mode) setMode(p.mode);
  setTab(p.action === "paraphrase" ? "para" : "check");
  if (src.value.trim()) (tab === "para" ? runPara() : runCheck());
  else src.focus();
};

function setTab(t) {
  tab = t;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === t));
  $("#pane-check").hidden = t !== "check";
  $("#pane-para").hidden = t !== "para";
}
function setMode(m) {
  mode = m;
  document.querySelectorAll(".mode").forEach((x) => x.classList.toggle("active", x.dataset.mode === m));
}

/* ---------- check ---------- */
async function runCheck() {
  const text = src.value, my = ++seq;
  if (!text.trim()) return;
  $("#busy-check").hidden = false;
  $("#busy-check").textContent = "Checking…";
  try {
    // Phase 1: LanguageTool only (instant). Phase 2: + AI (a few seconds).
    const quick = await api("/api/check", { text, use_llm: false });
    if (my !== seq || src.value !== text) return;
    issues = quick.issues;
    $("#busy-check").textContent = "AI checking…";
    renderIssues();
    const full = await api("/api/check", { text, model: pref("#m-check") });
    if (my !== seq || src.value !== text) return;
    issues = full.issues;
    $("#busy-check").hidden = true;
    renderIssues(full.errors);
  } catch (e) {
    $("#iss").innerHTML = `<p class="errors">${esc(e.message)}</p>`;
  } finally {
    if (my === seq) $("#busy-check").hidden = true;
  }
}
function renderIssues(errors = []) {
  const text = src.value;
  issues = issues.filter((i) => i.scope !== "sentence");
  updateStats();
  $("#n-iss").textContent = issues.length;
  $("#btn-fixall").disabled = !issues.some((i) => i.replacements.length);
  $("#iss").innerHTML = issues.map((it, i) => {
    const orig = text.slice(it.offset, it.offset + it.length);
    const addw = it.kind === "spelling" && /^[\p{L}'’-]+$/u.test(orig)
      ? `<div class="foot"><span></span><button class="link addw" data-w="${esc(orig)}">Add to dictionary</button></div>` : "";
    return `<div class="sugg k-${it.kind}">
      <div class="kind">${it.kind} · ${it.source}</div>
      <div class="line"><del>${esc(orig)}</del>${it.replacements.slice(0, 3).map((r, j) => ` → <button class="rep" data-i="${i}" data-r="${j}">${esc(r) || "(remove)"}</button>`).join(" ")}</div>
      <p class="msg">${esc(it.message)}</p>${addw}</div>`;
  }).join("") + (errors.length ? `<p class="errors">${esc(errors.join(" · "))}</p>` : "")
    + (!issues.length && text.trim() && $("#busy-check").hidden ? '<p class="muted small">No issues found.</p>' : "");
}
function replaceRange(start, end, rep) {
  src.focus(); src.setSelectionRange(start, end);
  if (!document.execCommand("insertText", false, rep)) src.value = src.value.slice(0, start) + rep + src.value.slice(end);
}
function applyFix(i, r) {
  const it = issues[i], rep = it.replacements[r], delta = rep.length - it.length;
  issues.splice(i, 1);
  issues = issues.map((x) => (x.offset > it.offset ? { ...x, offset: x.offset + delta } : x));
  replaceRange(it.offset, it.offset + it.length, rep);
  renderIssues();
}
function applyAll() {
  [...issues].filter((x) => x.replacements.length).sort((a, b) => b.offset - a.offset)
    .forEach((it) => replaceRange(it.offset, it.offset + it.length, it.replacements[0]));
  issues = []; renderIssues(); runCheck();
}
let pending = null; // promise of a running AI fix / rewrite; Replace waits for it
function track(p) { pending = p; p.finally(() => { if (pending === p) pending = null; }); return p; }
function aiFix() { return track(aiFixRun()); }
async function aiFixRun() {
  const text = src.value, my = ++seq;
  if (!text.trim()) return;
  const b = $("#btn-aifix"); b.disabled = true; b.textContent = "Fixing…";
  try {
    const res = await api("/api/paraphrase", { text, mode: "fix", model: pref("#m-para") });
    if (my !== seq || src.value !== text) return;
    replaceRange(0, src.value.length, res.text);
    issues = []; renderIssues(); runCheck();
  } catch (e) { $("#iss").innerHTML = `<p class="errors">${esc(e.message)}</p>`; }
  finally { b.disabled = false; b.textContent = "AI fix"; }
}

/* ---------- paraphrase ---------- */
function runPara() { return track(runParaRun()); }
async function runParaRun() {
  const text = src.value, my = ++seq, out = $("#para-out");
  if (!text.trim()) return;
  out.className = "para-out muted"; out.textContent = "Rewriting… (the first run loads the model)";
  paraText = "";
  try {
    $("#para-warn").textContent = "";
    const res = await api("/api/paraphrase", { text, mode, strength: +$("#strength").value, freeze, model: pref("#m-para") });
    if (res.missing_frozen && res.missing_frozen.length) $("#para-warn").textContent = "Changed despite freeze: " + res.missing_frozen.join(", ");
    if (my !== seq) return;
    paraText = res.text;
    out.className = "para-out has"; out.innerHTML = diffHtml(text, res.text);
  } catch (e) { if (my === seq) { out.className = "para-out"; out.textContent = "Error: " + e.message; } }
}
function diffHtml(a, b) {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
  if (A.length * B.length > 4e6) return esc(b);
  const n = A.length, m = B.length, L = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  let i = 0, j = 0, html = "";
  while (j < m) {
    if (i < n && A[i] === B[j]) { html += esc(B[j]); i++; j++; }
    else if (i < n && L[i + 1][j] >= L[i][j + 1]) i++;
    else { html += /^\s+$/.test(B[j]) ? esc(B[j]) : `<ins>${esc(B[j])}</ins>`; j++; }
  }
  return html;
}

/* ---------- output ---------- */
function result() { return tab === "para" && paraText ? paraText : src.value; }
async function replaceInApp() {
  const btn = $("#btn-replace");
  if (pending) {
    btn.disabled = true; btn.textContent = "Waiting for AI…";
    try { await pending; } catch {}
    btn.disabled = false; btn.textContent = "Replace in app";
  }
  const text = result();
  if (!text) return;
  try {
    if (desk()) await desk().replace(text);
    else await navigator.clipboard.writeText(text);
  } catch (e) { log("replace failed: " + e); }
}
function log(msg) { try { desk() && desk().log(String(msg)); } catch {} }
window.addEventListener("error", (e) => log(e.message));
window.addEventListener("pywebviewready", () => log("bridge ready"));
function closePopup() { seq++; desk() ? desk().close() : window.close(); }

/* ---------- events ---------- */
document.addEventListener("click", (e) => {
  const rep = e.target.closest(".rep[data-r]");
  if (rep) return applyFix(+rep.dataset.i, +rep.dataset.r);
  const t = e.target.closest(".tab");
  if (t) { setTab(t.dataset.tab); if (tab === "para" && !paraText) runPara(); return; }
  const m = e.target.closest(".mode");
  if (m) { setMode(m.dataset.mode); runPara(); }
});
src.addEventListener("input", () => {
  issues = []; paraText = ""; renderIssues();
  clearTimeout(editTimer);
  editTimer = setTimeout(() => (tab === "check" ? runCheck() : runPara()), 1200);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { e.preventDefault(); closePopup(); }
  if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); replaceInApp(); }
});
$("#btn-check").onclick = runCheck;
$("#btn-fixall").onclick = applyAll;
$("#btn-aifix").onclick = aiFix;
$("#btn-replace").onclick = replaceInApp;
$("#btn-copy").onclick = () => navigator.clipboard.writeText(result());
$("#close").onclick = closePopup;
$("#off-here").onclick = () => desk() && desk().disable_app();

$("#modes").innerHTML = Object.keys(MODE_LABELS).map((m) => `<button class="mode" data-mode="${m}">${MODE_LABELS[m]}</button>`).join("");
setMode(mode);

/* ---------- stats, slider, freeze words, dictionary ---------- */
const STRENGTH_LABELS = ["Minimal", "Light", "Medium", "Strong", "Max"];
let freeze = [];
function updateStats() {
  const st = textStats(src.value);
  $("#pstats").textContent = st.words ? `${st.words} words · ${st.reading} · ${st.label}` : "Ctrl+Enter · Esc";
}
function renderFreeze() {
  $("#freeze-list").innerHTML = freeze.map((f, i) => `<span class="chip-x">${esc(f)}<button data-f="${i}">×</button></span>`).join("");
  try { localStorage.setItem("pw-freeze", JSON.stringify(freeze)); } catch {}
}
$("#freeze-in").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  e.preventDefault(); e.stopPropagation();
  for (const part of e.target.value.split(",")) { const w = part.trim(); if (w && !freeze.includes(w)) freeze.push(w); }
  e.target.value = ""; renderFreeze();
});
$("#freeze-list").addEventListener("click", (e) => { const b = e.target.closest("button[data-f]"); if (b) { freeze.splice(+b.dataset.f, 1); renderFreeze(); } });
$("#strength").addEventListener("input", (e) => {
  $("#strength-label").textContent = STRENGTH_LABELS[e.target.value - 1];
  try { localStorage.setItem("pw-strength", e.target.value); } catch {}
});
$("#strength").addEventListener("change", () => { if (tab === "para") runPara(); });
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".addw");
  if (!b) return;
  await api("/api/dictionary", { word: b.dataset.w });
  const w = b.dataset.w.toLowerCase();
  issues = issues.filter((x) => !(x.kind === "spelling" && src.value.slice(x.offset, x.offset + x.length).toLowerCase() === w));
  renderIssues();
});
src.addEventListener("input", updateStats);
try { freeze = JSON.parse(localStorage.getItem("pw-freeze") || "[]"); } catch { freeze = []; }
try { $("#strength").value = JSON.parse(localStorage.getItem("pw-strength") || "3"); } catch {}
$("#strength-label").textContent = STRENGTH_LABELS[$("#strength").value - 1];
renderFreeze();
updateStats();
