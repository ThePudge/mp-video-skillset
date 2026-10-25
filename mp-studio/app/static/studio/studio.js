// MP Studio — by @mohammadpour.bi (MIT). Vanilla JS, talks to app/studio.py.
const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (url, opt = {}) => {
  const r = await fetch(url, { headers: opt.body && !(opt.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opt });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const put = (url, data) => api(url, { method: "PUT", body: JSON.stringify(data) });
const post = (url, data) => api(url, { method: "POST", body: data instanceof FormData ? data : JSON.stringify(data || {}) });
const params = new URLSearchParams(location.hash.slice(1));
let P = params.get("project") || localStorage.getItem("mp.project") || "";
let brand = {}, fontsCat = {}, lastReviewAt = 0;

const STATUS = {
  collecting: "فایل‌ها و هدف ویدیو را آماده کن، بعد «ارسال به Claude» را بزن",
  ready: "ذخیره شد ✓ — حالا در Claude بنویس: «پروژه رو ادیت کن» (یا اگه منتظره، خودش شروع می‌کنه)",
  working: "Claude در حال کار است…",
  review: "برنامه و استوری‌بورد آماده است — به «بازبینی» برو",
  approved: "تأیید ثبت شد ✓ — در Claude بنویس «تأیید کردم، نسخه نهایی رو بساز»",
  changes: "تغییرات ثبت شد ✓ — در Claude بنویس «تغییرات رو اعمال کن»",
  rendering: "در حال ساخت نسخه نهایی…",
  done: "تمام شد ✓ — خروجی آماده است",
};

// ---------------------------------------------------------------- media without download managers
// IDM & co. grab any request that looks like a video/audio file. Players load bytes from /blob/ (no
// extension, octet-stream) and play them from an in-page Blob URL, so nothing is intercepted.
const b64 = s => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const blobCache = new Map();
async function blobURL(area, file, type) {
  const key = `${P}|${area}|${file}`;
  if (blobCache.has(key)) URL.revokeObjectURL(blobCache.get(key));
  const r = await fetch(`/blob/${area}/${encodeURIComponent(P)}/${b64(file)}`, { cache: "no-store" });
  if (!r.ok) throw new Error("not found");
  const url = URL.createObjectURL(new Blob([await r.arrayBuffer()], { type }));
  blobCache.set(key, url);
  return url;
}
const TYPE = f => /\.(m4a|aac|mp3|wav|ogg|opus)$/i.test(f) ? "audio/mp4" : "video/mp4";

// ---------------------------------------------------------------- tabs
function show(tab) {
  $$("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $$(".tab").forEach(t => t.classList.toggle("on", t.id === "tab-" + tab));
  if (tab === "review") loadReview();
  if (tab === "voice") loadVoice();
  if (tab === "outputs") loadOutputs();
  if (tab === "learn") loadLearn();
  if (tab === "home") loadHealth();
}
$$("#tabs button").forEach(b => b.onclick = () => show(b.dataset.tab));

// ---------------------------------------------------------------- projects
async function loadProjects() {
  const list = await api("/api/projects");
  if (!P && list.length) P = list[list.length - 1].name;
  $("#project").innerHTML = list.map(p => `<option ${p.name === P ? "selected" : ""}>${p.name}</option>`).join("") || "<option value=''>— پروژه‌ای نیست —</option>";
  if (P) selectProject(P);
}
async function selectProject(name) {
  P = name; localStorage.setItem("mp.project", P); vLoadedFor = "";
  await Promise.all([loadFiles(), loadBrief(), pollHandoff(), baseBrand.colors && loadBrand()]);
  if ($("#tab-voice").classList.contains("on")) loadVoice();
}
$("#project").onchange = e => selectProject(e.target.value);
$("#newProject").onclick = async () => {
  const n = prompt("نام پروژه (انگلیسی یا فارسی، بدون علامت):");
  if (!n) return;
  const p = await post("/api/projects", { name: n });
  P = p.name; await loadProjects(); show("project");
};

// ---------------------------------------------------------------- files + brief
async function loadFiles() {
  if (!P) return;
  const f = await api(`/api/studio/projects/${P}/files`);
  $$(".drop[data-kind]").forEach(d => $("ul", d).innerHTML = (f[d.dataset.kind] || []).map(x => `<li>${x}</li>`).join(""));
  $("#links").innerHTML = f.links.map(l => `<li>${l}</li>`).join("");
  loadClips();
}

// ---------------------------------------------------------------- clip order + roles (drag to reorder)
const ROLE_FA = { main: "اصلی", retake: "تکرار", broll: "بی‌رول" };
async function loadClips() {
  const list = await api(`/api/studio/projects/${P}/clips`);
  const ol = $("#clipOrder");
  ol.innerHTML = list.length ? list.map(c => `
    <li draggable="true" data-file="${c.file}" data-role="${c.role}">
      <span class="grip">☰</span><span class="name" title="${c.file}">${c.file}</span>
      <select>${Object.entries(ROLE_FA).map(([v, l]) => `<option value="${v}" ${v === c.role ? "selected" : ""}>${l}</option>`).join("")}</select>
    </li>`).join("") : `<li class="muted" draggable="false">هنوز ویدیویی نیست</li>`;
  $$("#clipOrder li[data-file]").forEach(li => {
    $("select", li).onchange = e => { li.dataset.role = e.target.value; saveClips(); };
    li.ondragstart = e => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", li.dataset.file); li.classList.add("dragging"); };
    li.ondragend = () => { li.classList.remove("dragging"); $$("#clipOrder li").forEach(x => x.classList.remove("over")); saveClips(); };
    li.ondragover = e => {
      e.preventDefault();
      const d = $("#clipOrder li.dragging"); if (!d || d === li) return;
      const r = li.getBoundingClientRect();
      li.parentElement.insertBefore(d, e.clientY < r.top + r.height / 2 ? li : li.nextSibling);
    };
  });
}
async function saveClips() {
  const body = $$("#clipOrder li[data-file]").map(li => ({ file: li.dataset.file, role: li.dataset.role }));
  await put(`/api/studio/projects/${P}/clips`, body);
}
function wireDrop(el, onFiles) {
  const inp = $("input[type=file]", el);
  inp.onchange = () => onFiles(inp.files);
  el.ondragover = e => { e.preventDefault(); el.classList.add("over"); };
  el.ondragleave = () => el.classList.remove("over");
  el.ondrop = e => { e.preventDefault(); el.classList.remove("over"); onFiles(e.dataTransfer.files); };
}
$$(".drop[data-kind]").forEach(el => wireDrop(el, async files => {
  if (!P) return alert("اول یک پروژه بساز");
  const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
  job(true, "در حال آپلود…");
  try { await post(`/api/studio/projects/${P}/upload?kind=${el.dataset.kind}`, fd); } finally { job(false); }
  loadFiles();
}));
$("#addLink").onclick = async () => {
  if (!P) return;
  await post(`/api/studio/projects/${P}/link`, { url: $("#refLink").value.trim() }).catch(e => alert(e.message));
  $("#refLink").value = ""; loadFiles();
};
const BRIEF = ["topic", "goal", "cta", "length", "kind", "notes"];
// edit mode: "pro" = Claude Code (full power), "lite" = simpler / free agents (AGENTS.md, two commands)
const mode = () => ($('input[name="mode"]:checked') || {}).value || "pro";
const briefBody = () => ({ ...Object.fromEntries(BRIEF.map(k => [k, $("#b_" + k).value])), mode: mode() });
function showMode() {
  $("#sendClaude").textContent = mode() === "lite" ? "ذخیره و آماده برای ادیت سبک ✓" : "ذخیره و آماده برای Claude ✓";
}
async function loadBrief() {
  const b = await api(`/api/studio/projects/${P}/brief`);
  BRIEF.forEach(k => $("#b_" + k).value = b[k] || ($("#b_" + k).tagName === "SELECT" ? $("#b_" + k).options[0].value : ""));
  const m = $(`input[name="mode"][value="${b.mode === "lite" ? "lite" : "pro"}"]`); if (m) m.checked = true;
  showMode();
}
let briefTimer;
const saveBrief = () => { clearTimeout(briefTimer); briefTimer = setTimeout(() => P && put(`/api/studio/projects/${P}/brief`, briefBody()), 400); };
BRIEF.forEach(k => $("#b_" + k).oninput = saveBrief);
$$('input[name="mode"]').forEach(r => r.onchange = () => { showMode(); saveBrief(); });

// ---------------------------------------------------------------- handoff (whose turn it is)
async function pollHandoff() {
  if (!P) { $("#handoffText").textContent = "پروژه‌ای انتخاب نشده"; return; }
  const h = await api(`/api/studio/projects/${P}/handoff`);
  $("#handoffText").textContent = `${P}: ${STATUS[h.status] || h.status}`;
  $("#sendClaude").disabled = ["working", "approved", "rendering"].includes(h.status);
  $("#reviewDot").hidden = h.status !== "review";
  if (h.status === "review" && h.updated > lastReviewAt) { lastReviewAt = h.updated; show("review"); }
  if (h.status === "done" && h.updated > lastReviewAt) { lastReviewAt = h.updated; show("outputs"); }
}
setInterval(pollHandoff, 3000);
// After saving, say plainly what to do next: a ready-made sentence to paste into Claude.
function tellClaude(title, sentence) {
  $("#tellTitle").textContent = title;
  $("#tellText").value = sentence;
  $("#tellCopy").textContent = "کپی";
  $("#tellClaude").hidden = false;
}
$("#tellCopy").onclick = async () => {
  try { await navigator.clipboard.writeText($("#tellText").value); } catch { $("#tellText").select(); document.execCommand("copy"); }
  $("#tellCopy").textContent = "کپی شد ✓";
};
$("#tellClose").onclick = () => $("#tellClaude").hidden = true;
$("#tellClaude").onclick = e => { if (e.target.id === "tellClaude") $("#tellClaude").hidden = true; };
$("#sendClaude").onclick = async () => {
  if (!P) return alert("اول یک پروژه بساز");
  await put(`/api/studio/projects/${P}/brief`, briefBody());
  await put(`/api/studio/projects/${P}/handoff`, { status: "ready" });
  pollHandoff();
  if (mode() === "lite")
    tellClaude("ذخیره شد ✓ — حالت سبک", `پروژه‌ی «${P}» رو با حالت سبک ادیت کن: AGENTS.md رو بخون و lite_edit.py رو اجرا کن، اول استوری‌بورد، رندر فقط بعد از تأیید من`);
  else tellClaude("ذخیره شد ✓ — حالت حرفه‌ای (Claude)", `پروژه‌ی «${P}» رو ادیت کن`);
};

// ---------------------------------------------------------------- brand & style
const CHOICES = {
  theme: [["futuristic", "فضایی", "linear-gradient(135deg,#05060B,#1a2050 60%,#4DD8FF55)"], ["apple-dark", "اپل تیره", "#000"],
          ["apple-light", "اپل روشن", "#F5F5F7"], ["editorial", "ادیتوریال", "#F3F0EA"], ["editorial-dark", "ادیتوریال تیره", "#1C1C1E"]],
  card_style: [["glass", "شیشه‌ای", "linear-gradient(135deg,#ffffff40,#ffffff10)"], ["solid", "توپر", "#2b2b30"],
               ["outline", "خطی", "transparent"], ["paper", "کاغذی", "#FFFDF8"]],
  motion_feel: [["punchy", "ضربه‌ای سه‌بعدی (بدون فنر)", "linear-gradient(90deg,#111 30%,#FFC400)"], ["playful", "فنری و بازیگوش", "linear-gradient(90deg,#FFC400,#FF6B6B)"]],
  captions: [["emphasis", "کلمه کلیدی بزرگ", "#111"], ["word", "تک‌کلمه", "#111"], ["boxed", "داخل کادر", "#111"], ["glass", "شیشه‌ای", "linear-gradient(135deg,#ffffffcc,#ffffff66)"], ["glass-futuristic", "شیشه‌ای فضایی", "linear-gradient(135deg,#10142899,#4DD8FF55)"], ["off", "بدون زیرنویس", "#888"]],
  voice_preset: [["light", "صدا: سبک", "#2b3a2b"], ["clean", "صدا: تمیز", "#24452f"], ["strong", "صدا: قوی", "#1f5a33"], ["podcast", "صدا: پادکستی", "#5a3a1f"], ["off", "بدون پاک‌سازی", "#888"]],
};
function renderChoices() {
  for (const [key, opts] of Object.entries(CHOICES)) {
    $("#" + key).innerHTML = opts.map(([v, label, bg]) =>
      `<div class="choice ${brand[key] === v ? "on" : ""}" data-v="${v}"><div class="sw" style="background:${bg};${v === "outline" ? "border:2px solid #888" : ""}"></div>${label}</div>`).join("");
    $$(".choice", $("#" + key)).forEach(c => c.onclick = () => {
      brand[key] = c.dataset.v;
      // a new voice preset brings its own slider values (the Voice tab can fine-tune them afterwards)
      if (key === "voice_preset" && VPRESETS[c.dataset.v]) brand.voice = { ...(brand.voice || {}), settings: presetValues(c.dataset.v) };
      renderChoices(); saveBrand();
    });
  }
}
// Brand & style edit either the brand (every project) or only the current project: work/<project>/settings.json
// keeps just what differs from the brand. Page, name, bio, photo and logo are always brand-wide.
let scope = "brand", baseBrand = {}, overrides = {};
const SIMPLE = ["page", "name", "bio", "cta", "pace", "music_end", "language"];
const IDENTITY_FIELDS = ["#s_page", "#s_name", "#s_bio"];
async function loadBrand() {
  baseBrand = await api("/api/studio/brand");
  const s = P ? await api(`/api/studio/projects/${P}/settings`) : { overrides: {}, effective: baseBrand };
  overrides = s.overrides;
  if (scope === "project" && !P) scope = "brand";
  brand = structuredClone(scope === "project" ? s.effective : baseBrand);
  SIMPLE.forEach(k => $("#s_" + k).value = brand[k] || "");
  ["accent", "accent2", "text", "dark"].forEach(k => $("#c_" + k).value = brand.colors[k]);
  showPic("avatar", brand.avatar); showPic("logo", brand.logo);
  renderChoices(); renderScope(); await loadFonts();
}
function renderScope() {
  const n = Object.keys(overrides).length, proj = scope === "project";
  $$("#scope button").forEach(b => b.classList.toggle("on", b.dataset.s === scope));
  $(".scopeBar").classList.toggle("project", proj);
  $$(".pname").forEach(x => x.textContent = P || "—");
  $("#scopeNote").textContent = proj
    ? (n ? `${n} مورد با برند فرق دارد — فقط روی همین پروژه اثر دارد` : "هنوز مثل برند است؛ هر چه تغییر بدهی فقط برای همین پروژه ذخیره می‌شود")
    : (n && P ? `پروژه‌ی «${P}» ${n} تنظیم مخصوص خودش دارد` : "روی همه‌ی پروژه‌ها اثر دارد");
  $("#resetProject").hidden = !(proj && n);
  [$(".avatarRow"), ...IDENTITY_FIELDS.map(s => $(s).closest("label"))].forEach(el => el.classList.toggle("locked", proj));
}
$$("#scope button").forEach(b => b.onclick = () => {
  if (b.dataset.s === "project" && !P) return alert("اول یک پروژه بساز");
  scope = b.dataset.s; loadBrand();
});
$("#resetProject").onclick = async () => {
  if (!confirm(`تنظیمات مخصوص «${P}» پاک شود و پروژه مثل برند شود؟`)) return;
  await put(`/api/studio/projects/${P}/settings`, {}); loadBrand();
};
let brandTimer;
function saveBrand() {
  clearTimeout(brandTimer);
  brandTimer = setTimeout(async () => {
    SIMPLE.forEach(k => brand[k] = $("#s_" + k).value);
    ["accent", "accent2", "text", "dark"].forEach(k => brand.colors[k] = $("#c_" + k).value);
    ["captions", "keyword", "display", "contrast"].forEach(k => brand.fonts[k] = $("#f_" + k).value);
    if (scope === "project") {
      const s = await put(`/api/studio/projects/${P}/settings`, brand);
      brand = s.effective; overrides = s.overrides; renderScope();
    } else {
      brand = baseBrand = await put("/api/studio/brand", brand);
    }
    $("#savedNote").textContent = scope === "project" ? `ذخیره شد ✓ (فقط «${P}»)` : "ذخیره شد ✓";
    $("#savedNote").hidden = false; setTimeout(() => $("#savedNote").hidden = true, 1400);
    previewFonts();
  }, 350);
}
[...SIMPLE.map(k => "#s_" + k), ...["accent", "accent2", "text", "dark"].map(k => "#c_" + k)].forEach(s => $(s).oninput = saveBrand);
// profile photo / logo: an empty or failed image never shows as a broken icon
function showPic(kind, path) {
  const img = $("#" + kind);
  img.onerror = () => { img.hidden = true; img.nextElementSibling.hidden = false; };
  img.onload = () => { img.hidden = false; img.nextElementSibling.hidden = true; };
  if (path) img.src = "/brand-files/" + path.split("/").pop() + "?" + Date.now();
  else { img.hidden = true; img.removeAttribute("src"); img.nextElementSibling.hidden = false; }
}
async function uploadPic(kind, file) {
  $("#picError").hidden = true;
  const fd = new FormData(); fd.append("file", file);
  try { const r = await post(`/api/studio/brand/avatar?kind=${kind}`, fd); brand[kind] = r[kind]; showPic(kind, r[kind]); }
  catch (err) { $("#picError").textContent = "آپلود نشد: " + err.message; $("#picError").hidden = false; }
}
$("#logoFile").onchange = e => e.target.files[0] && uploadPic("logo", e.target.files[0]);
$("#avatarFile").onchange = async e => {
  if (e.target.files[0]) await uploadPic("avatar", e.target.files[0]);
};

// ---------------------------------------------------------------- fonts
const faceDone = new Set();
function face(fam) {
  const st = fontsCat[fam]; if (!st || faceDone.has(fam)) return;
  const file = st.styles.Bold || st.styles.Regular || Object.values(st.styles)[0];
  const f = new FontFace(fam, `url(/font-files/${encodeURIComponent(file)})`);
  f.load().then(x => document.fonts.add(x)).catch(() => {}); faceDone.add(fam);
}
async function loadFonts() {
  fontsCat = await api("/api/studio/fonts");
  const fams = Object.keys(fontsCat).sort();
  const opt = sel => `<option value="">—</option>` + fams.map(f => `<option ${f === sel ? "selected" : ""}>${f}</option>`).join("");
  ["captions", "keyword", "display", "contrast"].forEach(k => { $("#f_" + k).innerHTML = opt(brand.fonts[k]); $("#f_" + k).onchange = saveBrand; });
  const ROLE = { captions: "زیرنویس", display: "تیتر", contrast: "متضاد" };
  $("#fontList").innerHTML = fams.map(f => { face(f); return `<div><span style="font-family:'${f}'">${$("#sample").value}</span><small>${f} · ${Object.keys(fontsCat[f].styles).length} وزن · ${ROLE[fontsCat[f].role] || ""}</small></div>`; }).join("");
  previewFonts();
}
function previewFonts() {
  const s = $("#sample").value, F = brand.fonts || {};
  [F.captions, F.keyword, F.display, F.contrast].forEach(face);
  $("#fontPreview").innerHTML =
    `<div class="cap" style="font-family:'${F.captions}'">${s}</div>
     <div class="kw" style="font-family:'${F.keyword}';color:${brand.colors.accent}">${s.split(" ").slice(-2).join(" ")}</div>
     <div class="disp" style="font-family:'${F.display}'">۲۵۰٬۰۰۰ فالوور</div>` +
    (F.contrast ? `<div class="disp" style="font-family:'${F.contrast}'">${s.split(" ")[0]}</div>` : "");
}
$("#sample").oninput = () => { $$("#fontList span").forEach(x => x.textContent = $("#sample").value); previewFonts(); };
$("#fontFiles").onchange = async e => {
  const fd = new FormData(); [...e.target.files].forEach(f => fd.append("files", f));
  job(true, "در حال مرتب‌سازی فونت‌ها…");
  try { await post("/api/studio/fonts", fd); } finally { job(false); }
  loadFonts();
};

// ---------------------------------------------------------------- review
async function loadReview() {
  if (!P) return;
  const r = await api(`/api/studio/projects/${P}/review`);
  const has = r && r.cards && r.cards.length;
  $("#reviewEmpty").hidden = !!has; $("#reviewBody").hidden = !has;
  if (!has) return;
  $("#planText").textContent = r.plan || "";
  $("#reviewStage").textContent = r.stage === "storyboard" ? "استوری‌بورد — قبل از رندر (عکس‌ها از ویدیوی خام)" : "پیش‌نمایش رندر‌شده";
  $("#cutTable").innerHTML = r.cuts && r.cuts.length ? `<table><tr><th>#</th><th>از</th><th>تا</th><th>قبل از برش</th><th>بعد از برش</th></tr>` +
    r.cuts.map((c, i) => `<tr><td>${i + 1}</td><td dir="ltr">${c.start}</td><td dir="ltr">${c.end}</td><td>${c.before}</td><td>${c.after}</td></tr>`).join("") + "</table>" : "";
  $("#cards").innerHTML = r.cards.map((c, i) => `
    <div class="scard" data-i="${i}">
      <img src="/review-media/${P}/${c.still}" alt="" title="پخش این بخش">
      ${c.audio ? `<audio preload="none" data-f="${c.audio}"></audio>` : ""}
      <div class="meta"><span class="time">${c.t0.toFixed(1)}s → ${c.t1.toFixed(1)}s</span>
        <span class="words">${c.words || ""}</span><span><span class="tag">${c.layout || ""}</span></span><span class="move">${c.move || ""}</span>${c.clip ? `<span class="clip">🎞 ${c.clip}</span>` : ""}</div>
      <textarea rows="2" placeholder="یادداشت برای این صحنه…"></textarea>
    </div>`).join("");
  $$(".scard img").forEach(img => img.onclick = async () => {
    const a = $("audio", img.parentElement); if (!a) return;
    $$("audio").forEach(x => x !== a && x.pause());
    if (!a.src) a.src = await blobURL("review", a.dataset.f, "audio/mp4");
    a.currentTime = 0; a.play();
  });
}
async function decide(decision) {
  const cards = {}; $$(".scard").forEach(c => { const v = $("textarea", c).value.trim(); if (v) cards[c.dataset.i] = v; });
  await post(`/api/studio/projects/${P}/review/decision`, { decision, general: $("#generalNote").value, cards });
  $("#generalNote").value = ""; pollHandoff();
  if (decision === "approve") tellClaude("تأیید ثبت شد ✓", `پروژه‌ی «${P}»: تأیید کردم، نسخه نهایی رو بساز`);
  else tellClaude("تغییرات ثبت شد ✓", `پروژه‌ی «${P}»: یادداشت‌های بازبینی رو اعمال کن`);
}
$("#approve").onclick = () => decide("approve");
$("#requestChanges").onclick = () => decide("changes");

// ---------------------------------------------------------------- voice cleaner
const VPRESETS = {
  light:   { label: "سبک", sub: "میکروفون خوب، فقط صیقل", denoise: 0.5, deess: 0.3, presence: 1, warmth: 0, compress: 0.4, gate: 0 },
  clean:   { label: "تمیز", sub: "اتاق معمولی، یقه‌ای یا گوشی", denoise: 0.75, deess: 0.5, presence: 2, warmth: 1, compress: 0.6, gate: 0.3 },
  strong:  { label: "قوی", sub: "اتاق پرنویز، پنکه، کولر، خیابان", denoise: 0.95, deess: 0.5, presence: 2.5, warmth: 0.5, compress: 0.7, gate: 0.6 },
  podcast: { label: "پادکستی", sub: "گرم و رادیویی", denoise: 0.7, deess: 0.6, presence: 2, warmth: 2.5, compress: 0.85, gate: 0.3 },
};
const VOFF = { label: "بدون پاک‌سازی", sub: "صدا اصلاً دست نمی‌خورد" };
const VKEYS = ["denoise", "deess", "presence", "warmth", "compress", "gate"];
const presetValues = p => Object.fromEntries(VKEYS.map(k => [k, VPRESETS[p][k]]));
let vPreset = "clean", vLoadedFor = "";
function setPreset(p, values) {
  vPreset = p;
  $("#v_preset").innerHTML = Object.entries({ ...VPRESETS, off: VOFF }).map(([k, v]) =>
    `<div class="choice ${k === p ? "on" : ""}" data-v="${k}"><b>${v.label}</b><br><small class="muted">${v.sub}</small></div>`).join("");
  $$(".choice", $("#v_preset")).forEach(c => c.onclick = () => setPreset(c.dataset.v));
  const off = p === "off";
  [".sliders", "#v_dehum", "#v_preview", "#v_apply"].forEach(s => $(s).classList.toggle("locked", off));
  if (!off) VKEYS.forEach(k => { const x = (values || VPRESETS[p])[k] ?? VPRESETS[p][k]; $("#v_" + k).value = x; $("#o_" + k).textContent = x; });
}
VKEYS.forEach(k => $("#v_" + k).oninput = e => $("#o_" + k).textContent = e.target.value);
const vLabel = p => (VPRESETS[p] || VOFF).label;
// what this project's edits will use: project settings.json over brand.json (same merge as the server)
async function showVoiceUses(loadIntoSliders) {
  const s = await api(`/api/studio/projects/${P}/settings`);
  const e = s.effective, own = "voice_preset" in s.overrides || "voice" in s.overrides;
  const custom = e.voice_preset !== "off" && e.voice && e.voice.settings &&
    VKEYS.some(k => e.voice.settings[k] !== undefined && e.voice.settings[k] !== VPRESETS[e.voice_preset][k]);
  $("#v_uses").innerHTML = `ادیت‌های «${P}» با این صدا ساخته می‌شوند: <b>${vLabel(e.voice_preset)}</b>` +
    (custom ? " + تنظیم دستی" : "") + (e.voice_preset !== "off" && e.voice?.dehum === "off" ? " · وزوز خاموش" : "") +
    ` <span class="tag">${own ? "تنظیم همین پروژه" : "پیش‌فرض برند"}</span>`;
  if (loadIntoSliders) {
    setPreset(e.voice_preset in VPRESETS || e.voice_preset === "off" ? e.voice_preset : "clean", e.voice?.settings);
    $("#v_dehum").value = e.voice?.dehum || "auto";
  }
}
function voiceChoice() {
  return { voice_preset: vPreset, voice: vPreset === "off" ? {} :
           { settings: Object.fromEntries(VKEYS.map(k => [k, +$("#v_" + k).value])), dehum: $("#v_dehum").value } };
}
$("#v_useProject").onclick = async () => {
  if (!P) return alert("اول یک پروژه بساز");
  await put(`/api/studio/projects/${P}/settings`, { ...(await api(`/api/studio/projects/${P}/settings`)).effective, ...voiceChoice() });
  await showVoiceUses(false); loadBrand();
  tellClaude("ذخیره شد ✓", `پروژه‌ی «${P}» رو ادیت کن`);
};
$("#v_useBrand").onclick = async () => {
  const b = await api("/api/studio/brand");
  await put("/api/studio/brand", { ...b, ...voiceChoice() });
  if (P) { const s = await api(`/api/studio/projects/${P}/settings`); const o = s.overrides; delete o.voice_preset; delete o.voice; await put(`/api/studio/projects/${P}/settings`, { ...s.brand, ...o }); }
  await showVoiceUses(false); loadBrand();
  $("#savedNote").textContent = "ذخیره شد ✓ (همه‌ی پروژه‌ها)"; $("#savedNote").hidden = false; setTimeout(() => $("#savedNote").hidden = true, 1400);
};
async function loadVoice() {
  if (!P) return;
  const v = await api(`/api/studio/projects/${P}/voice`);
  $("#v_file").innerHTML = v.sources.map(f => `<option>${f}</option>`).join("") || "<option value=''>— اول در «پروژه» فایل بذار —</option>";
  $("#v_done").innerHTML = v.done.map(f => `<li><a href="/media/output/${P}/${f}" target="_blank">${f}</a></li>`).join("") || "<li>هنوز چیزی نیست</li>";
  await showVoiceUses(vLoadedFor !== P); vLoadedFor = P;
}
async function runVoice(preview) {
  if (vPreset === "off") return;
  if (!P || !$("#v_file").value) return alert("اول یک فایل انتخاب کن");
  const body = { file: $("#v_file").value, preset: vPreset, dehum: $("#v_dehum").value, lufs: +$("#v_lufs").value,
                 start: +$("#v_start").value, preview, settings: Object.fromEntries(VKEYS.map(k => [k, +$("#v_" + k).value])) };
  const j = await post(`/api/studio/projects/${P}/voice`, body);
  job(true, preview ? "پیش‌نمایش صدا…" : "پاک‌سازی کل فایل…");
  $("#v_result").textContent = "در حال پردازش…";
  const t = setInterval(async () => {
    const s = await api("/api/jobs/" + j.id);
    if (s.status !== "done" && s.status !== "error") return;
    clearInterval(t); job(false);
    if (s.error) { $("#v_result").textContent = "خطا: " + s.error; return; }
    const r = s.result, rep = r.report || {};
    $("#v_result").textContent = `صدا ${rep.snr_before} → ${rep.snr_after} دسی‌بل بالاتر از نویز اتاق` + (rep.hum ? ` · وزوز ${rep.hum} هرتز حذف شد` : "");
    $("#v_report").textContent = r.text;
    $("#v_players").hidden = false;
    const stamp = "?" + Date.now();
    if (preview) { $("#v_before").src = await blobURL("work", "voice_before.m4a", "audio/mp4"); $("#v_after").src = await blobURL("work", "voice_after.m4a", "audio/mp4"); }
    else { $("#v_after").src = await blobURL("output", r.file, TYPE(r.file)); loadVoice(); }
  }, 1000);
}
$("#v_preview").onclick = () => runVoice(true);
$("#v_apply").onclick = () => runVoice(false);
setPreset("clean");

// ---------------------------------------------------------------- outputs, learn, health
async function loadOutputs() {
  if (!P) return;
  const outs = await api(`/api/studio/projects/${P}/outputs`);
  $("#outList").innerHTML = outs.map(o => `<div class="card"><video controls preload="none" data-f="${o.file}"></video><button class="primary playBtn">▶ پخش</button>
    <div class="row"><b class="grow" dir="ltr">${o.file}</b><span class="muted">${o.mb} MB</span>
    <a class="btn" download href="/media/output/${P}/${o.file}">دانلود</a></div>
    ${o.caption ? `<label>کپشن و هشتگ<textarea rows="5">${o.caption}</textarea></label><button onclick="navigator.clipboard.writeText(this.previousElementSibling.querySelector('textarea').value)">کپی</button>` : ""}</div>`).join("") || `<div class="card muted">هنوز خروجی‌ای نیست.</div>`;
  $$(".playBtn").forEach(btn => btn.onclick = async () => {
    const v = btn.previousElementSibling;
    btn.textContent = "در حال بارگذاری…";
    try { v.src = await blobURL("output", v.dataset.f, "video/mp4"); btn.remove(); v.play(); }
    catch { btn.textContent = "پیدا نشد"; }
  });
}
async function loadLearn() {
  $("#learnList").innerHTML = (await api("/api/studio/learn")).map(x => `<li>${x}</li>`).join("") || "<li>خالی</li>";
}
wireDrop($("#learnDrop"), async files => { const fd = new FormData(); [...files].forEach(f => fd.append("files", f)); await post("/api/studio/learn", fd); loadLearn(); });
$("#learnSave").onclick = async () => { await post("/api/studio/learn/link", { url: $("#learnUrl").value, note: $("#learnNote").value }).catch(e => alert(e.message)); $("#learnUrl").value = $("#learnNote").value = ""; loadLearn(); };
async function loadHealth() {
  const h = await api("/api/studio/health");
  $("#health").innerHTML = h.map(c => `<li class="${c.ok ? "ok" : ""}">${c.label}</li>`).join("");
}
$("#refreshHealth").onclick = loadHealth;
$("#setupBtn").onclick = async () => {
  const j = await post("/api/studio/setup");
  $("#setupLog").hidden = false;
  const t = setInterval(async () => {
    const s = await api("/api/jobs/" + j.id);
    $("#setupLog").textContent = (s.log || []).join("\n"); $("#setupLog").scrollTop = 1e9;
    if (s.status === "done" || s.status === "error") { clearInterval(t); loadHealth(); if (s.error) alert(s.error); }
  }, 1200);
};
$$("[data-open]").forEach(b => b.onclick = () => post("/api/studio/open", { area: b.dataset.open, project: P }));
function job(on, text = "") { $("#job").hidden = !on; $("#jobText").textContent = text; $("#jobBar").removeAttribute("value"); }

// ---------------------------------------------------------------- start
loadProjects().then(loadBrand).then(() => show(params.get("tab") || "home"));
