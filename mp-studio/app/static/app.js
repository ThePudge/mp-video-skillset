"use strict";
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const fmt = (t) => { t = Math.max(0, t); const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${String(s).padStart(2, "0")}`; };

const S = {
  project: null, info: null,
  clips: [], cuts: null, ranges: [],
  words: [],          // flat: {id, ci, wi, s, e, el}
  byId: new Map(),
  sel: null,          // {a, b} indexes into S.words
  undo: [],
  clip: -1,           // clip loaded in <video>
  editPlay: false, rangeIdx: 0,
};
const video = $("video");

// ---------- projects ----------

async function loadProjects(select) {
  const list = await api("/api/projects");
  $("projectSelect").innerHTML = list.map((p) => `<option>${p.name}</option>`).join("");
  $("empty").hidden = list.length > 0;
  $("workspace").hidden = list.length === 0;
  $("projectSelect").hidden = list.length === 0;
  const want = select || localStorage.getItem("project");
  const name = list.some((p) => p.name === want) ? want : list[0]?.name;
  if (name) { $("projectSelect").value = name; await openProject(name); }
}

async function newProject() {
  const name = prompt("Project name (e.g. product-intro)");
  if (!name) return;
  const p = await api("/api/projects", { method: "POST", body: JSON.stringify({ name }) });
  await loadProjects(p.name);
}

async function openProject(name) {
  S.project = name;
  try { localStorage.setItem("project", name); } catch {}
  S.undo = []; S.sel = null; S.clip = -1; video.removeAttribute("src");
  await refreshInfo();
  await loadTimeline();
  pollJobs();
}

async function refreshInfo() {
  const p = (S.info = await api(`/api/projects/${enc()}`));
  $("clipList").innerHTML = p.clips.map((c) => `<li><span class="name" title="${c.file}">${c.file}</span>
      <span class="tag ${c.transcript ? "ok" : ""}">${c.transcript ? "ready" : c.proxy ? "needs transcript" : "new"}</span></li>`).join("")
    || `<li class="tag">No clips yet</li>`;
  $("outputList").innerHTML = p.outputs.filter((o) => !o.file.includes(".tmp.")).map((o) => {
    const url = `/media/output/${enc()}/${encodeURIComponent(o.file)}`;
    const play = o.file.endsWith(".mp4") ? `<a href="#" data-play="${url}">play</a>` : "";
    return `<li><span class="name" title="${o.file}">${o.file}</span>${play}<a href="${url}" download>save</a></li>`;
  }).join("") || `<li class="tag">Nothing rendered yet</li>`;
  $("processBtn").disabled = !p.clips.length;
}
const enc = () => encodeURIComponent(S.project);

// ---------- timeline / transcript ----------

async function loadTimeline() {
  const t = await api(`/api/projects/${enc()}/timeline`);
  S.clips = t.clips; S.cuts = t.cuts; S.ranges = t.ranges;
  $("maxPause").value = S.cuts.maxPause;
  $("maxPauseVal").textContent = `${S.cuts.maxPause}s`;
  $("srtLink").href = `/api/projects/${enc()}/srt`;
  $("srtLink").setAttribute("download", `${S.project}.srt`);
  buildTranscript();
  updateStats();
  $("renderBtn").disabled = !S.clips.length;
  if (S.clips.length && S.clip < 0) loadClip(0);
}

function buildTranscript() {
  const box = $("transcript");
  box.innerHTML = "";
  S.words = []; S.byId.clear();
  if (!S.clips.length) {
    box.innerHTML = `<p class="tag">${S.info?.clips.length ? "Click “Prepare & transcribe”." : "Add your raw videos on the left."}</p>`;
    return;
  }
  const removed = new Set(S.cuts.removed), kept = new Set(S.cuts.keptPauses);
  S.clips.forEach((clip, ci) => {
    const head = document.createElement("div");
    head.className = "clip-head";
    head.textContent = `${clip.file} · ${fmt(clip.duration)}`;
    box.appendChild(head);
    let wi = 0, prev = null;
    for (const seg of clip.segments) {
      const row = document.createElement("div");
      row.className = "seg";
      const txt = document.createElement("div");
      txt.className = "txt"; txt.dir = "auto";
      const first = S.words.length;
      for (const w of seg.words) {
        if (prev && w.s - prev.e > S.cuts.maxPause) {
          const pid = `${ci}:${wi - 1}`;
          const pz = document.createElement("span");
          pz.className = "pz " + (kept.has(pid) ? "keep" : "cut");
          pz.textContent = `⏸ ${(w.s - prev.e).toFixed(1)}s`;
          pz.title = "Click to keep or cut this pause";
          pz.onclick = () => togglePause(pid);
          txt.appendChild(pz);
        }
        const id = `${ci}:${wi}`;
        const el = document.createElement("span");
        el.className = "w" + (removed.has(id) ? " cut" : "");
        el.textContent = w.w;
        el.dataset.i = S.words.length;
        const rec = { id, ci, wi, s: w.s, e: w.e, el };
        S.words.push(rec); S.byId.set(id, rec);
        txt.appendChild(el); txt.appendChild(document.createTextNode(" "));
        prev = w; wi++;
      }
      const last = S.words.length - 1;
      const t = document.createElement("span");
      t.className = "t"; t.textContent = fmt(seg.s);
      t.onclick = () => seekWord(first);
      const x = document.createElement("button");
      x.className = "x"; x.textContent = "✕"; x.title = "Cut / restore this sentence";
      x.onclick = () => { S.sel = { a: first, b: last }; toggleSelection(); };
      row.append(t, txt, x);
      box.appendChild(row);
    }
  });
}

// mouse: click = seek + select, shift+click / drag = extend selection
let dragging = false;
$("transcript").addEventListener("mousedown", (e) => {
  const i = e.target.dataset?.i;
  if (i === undefined) return;
  const n = +i;
  S.sel = e.shiftKey && S.sel ? { a: S.sel.a, b: n } : { a: n, b: n };
  dragging = true;
  paintSel();
  if (!e.shiftKey) seekWord(n);
});
$("transcript").addEventListener("mouseover", (e) => {
  if (!dragging || e.target.dataset?.i === undefined) return;
  S.sel.b = +e.target.dataset.i; paintSel();
});
window.addEventListener("mouseup", () => (dragging = false));

function selRange() {
  if (!S.sel) return [];
  const [a, b] = [Math.min(S.sel.a, S.sel.b), Math.max(S.sel.a, S.sel.b)];
  return S.words.slice(a, b + 1);
}
function paintSel() {
  document.querySelectorAll(".w.sel").forEach((el) => el.classList.remove("sel"));
  selRange().forEach((w) => w.el.classList.add("sel"));
}

function pushUndo() {
  S.undo.push(JSON.stringify(S.cuts));
  if (S.undo.length > 100) S.undo.shift();
}
function setCut(words, cut) {
  if (!words.length) return;
  pushUndo();
  const set = new Set(S.cuts.removed);
  words.forEach((w) => { cut ? set.add(w.id) : set.delete(w.id); w.el.classList.toggle("cut", cut); });
  S.cuts.removed = [...set];
  saveCuts();
}
function toggleSelection() {
  const ws = selRange();
  const allCut = ws.length && ws.every((w) => w.el.classList.contains("cut"));
  setCut(ws, !allCut);
  paintSel();
}
function togglePause(pid) {
  pushUndo();
  const set = new Set(S.cuts.keptPauses);
  set.has(pid) ? set.delete(pid) : set.add(pid);
  S.cuts.keptPauses = [...set];
  buildTranscript(); paintSel(); saveCuts();
}
function undo() {
  if (!S.undo.length) return;
  S.cuts = JSON.parse(S.undo.pop());
  $("maxPause").value = S.cuts.maxPause;
  $("maxPauseVal").textContent = `${S.cuts.maxPause}s`;
  buildTranscript(); paintSel(); saveCuts();
}

let saveTimer;
function saveCuts() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const r = await api(`/api/projects/${enc()}/cuts`, { method: "PUT", body: JSON.stringify(S.cuts) });
    S.ranges = r.ranges;
    updateStats();
  }, 250);
}

function updateStats() {
  const orig = S.clips.reduce((a, c) => a + c.duration, 0);
  const edit = S.ranges.reduce((a, r) => a + r.e - r.s, 0);
  $("stats").textContent = S.clips.length ? `${fmt(orig)} → ${fmt(edit)} (${S.ranges.length} pieces)` : "";
}

// ---------- playback ----------

function loadClip(ci, at = 0, play = false) {
  const clip = S.clips[ci];
  if (!clip) return;
  const go = () => { video.currentTime = at; if (play) video.play(); };
  if (S.clip === ci) return go();
  S.clip = ci;
  video.src = `/media/work/${enc()}/${encodeURIComponent(clip.stem)}.proxy.mp4`;
  video.addEventListener("loadedmetadata", go, { once: true });
}
function seekWord(i) {
  const w = S.words[i];
  if (!w) return;
  S.editPlay = false; setEditBtn();
  loadClip(w.ci, w.s, !video.paused);
}

function playEdit() {
  if (S.editPlay) { S.editPlay = false; video.pause(); setEditBtn(); return; }
  if (!S.ranges.length) return;
  // continue from the range at/after the playhead, else from the start
  const t = video.currentTime;
  let i = S.ranges.findIndex((r) => r.clip === S.clip && r.e > t);
  if (i < 0) i = 0;
  S.rangeIdx = i; S.editPlay = true; setEditBtn();
  const r = S.ranges[i];
  loadClip(r.clip, r.clip === S.clip && t > r.s && t < r.e ? t : r.s, true);
}
function setEditBtn() { $("playEdit").textContent = S.editPlay ? "❚❚ Stop edit" : "▶ Play edit"; }

let nowEl = null;
function tick() {
  if (S.clip >= 0) {
    const t = video.currentTime;
    if (S.editPlay && !video.paused) {
      const r = S.ranges[S.rangeIdx];
      if (!r || r.clip !== S.clip || t >= r.e - 0.02 || t < r.s - 0.3) {
        const next = r && r.clip === S.clip && t < r.s - 0.3 ? S.rangeIdx : S.rangeIdx + 1;
        const n = S.ranges[next];
        if (!n) { S.editPlay = false; video.pause(); setEditBtn(); }
        else { S.rangeIdx = next; loadClip(n.clip, n.s, true); }
      }
    }
    // highlight the word under the playhead
    const cur = S.words.find((w) => w.ci === S.clip && w.s <= t && t < w.e);
    if (cur?.el !== nowEl) {
      nowEl?.classList.remove("now");
      nowEl = cur?.el || null;
      if (nowEl) {
        nowEl.classList.add("now");
        if (!video.paused) nowEl.scrollIntoView({ block: "nearest" });
      }
    }
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// ---------- upload / jobs / render ----------

function upload(files) {
  const fd = new FormData();
  [...files].forEach((f) => fd.append("files", f));
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/projects/${enc()}/upload`);
  showJob("Uploading…", 0);
  xhr.upload.onprogress = (e) => e.lengthComputable && showJob("Uploading…", e.loaded / e.total);
  xhr.onload = async () => { hideJob(); await refreshInfo(); };
  xhr.onerror = () => showJob("Upload failed", 0, true);
  xhr.send(fd);
}

function showJob(text, p, err) {
  $("jobBar").hidden = false;
  $("jobText").textContent = text;
  $("jobText").className = err ? "err" : "";
  $("jobProgress").value = p;
}
function hideJob() { $("jobBar").hidden = true; }

let polling = false;
async function pollJobs() {
  if (polling) return;
  polling = true;
  try {
    for (;;) {
      const jobs = await api(`/api/jobs?project=${enc()}`);
      const active = jobs.find((j) => j.status === "running" || j.status === "queued");
      const last = jobs[0];
      if (active) {
        showJob(`${active.message || active.kind} ${Math.round(active.progress * 100)}%`, active.progress);
        $("processBtn").disabled = $("renderBtn").disabled = true;
      } else {
        if (last?.status === "error") showJob(`${last.kind} failed: ${last.error}`, 0, true);
        else hideJob();
        $("processBtn").disabled = !S.info?.clips.length;
        $("renderBtn").disabled = !S.clips.length;
        if (last && last.status !== "error") {
          await refreshInfo();
          if (last.kind === "process") await loadTimeline();
        }
        break;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  } finally { polling = false; }
}

async function startProcess() {
  await api(`/api/projects/${enc()}/process`, {
    method: "POST", body: JSON.stringify({ model: $("model").value, language: $("language").value }),
  });
  pollJobs();
}
async function startRender() {
  try {
    await api(`/api/projects/${enc()}/render`, {
      method: "POST",
      body: JSON.stringify({ aspect: $("aspect").value, loudnorm: $("loudnorm").checked, denoise: $("denoise").checked }),
    });
    pollJobs();
  } catch (e) { showJob(e.message, 0, true); }
}

// ---------- wiring ----------

$("projectSelect").onchange = (e) => openProject(e.target.value);
$("newProject").onclick = $("newProject2").onclick = newProject;
$("fileInput").onchange = (e) => upload(e.target.files);
const drop = $("drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); };
for (const id of ["model", "language", "aspect"]) {
  try { const v = localStorage.getItem(id); if (v !== null) $(id).value = v; } catch {}
  $(id).addEventListener("change", (e) => { try { localStorage.setItem(id, e.target.value); } catch {} });
}
$("processBtn").onclick = startProcess;
$("renderBtn").onclick = startRender;
$("playEdit").onclick = playEdit;
$("removeSel").onclick = () => { setCut(selRange(), true); paintSel(); };
$("restoreSel").onclick = () => { setCut(selRange(), false); paintSel(); };
$("undoBtn").onclick = undo;
$("maxPause").oninput = (e) => {
  pushUndo();
  S.cuts.maxPause = +e.target.value;
  $("maxPauseVal").textContent = `${S.cuts.maxPause}s`;
  buildTranscript(); paintSel(); saveCuts();
};
$("outputList").onclick = (e) => {
  const url = e.target.dataset?.play;
  if (!url) return;
  e.preventDefault();
  S.editPlay = false; setEditBtn(); S.clip = -1;
  video.src = url; video.play();
};
window.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); toggleSelection(); }
  else if (e.key === " ") { e.preventDefault(); video.paused ? video.play() : video.pause(); }
  else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
});

loadProjects();
