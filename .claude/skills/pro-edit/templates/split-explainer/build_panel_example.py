"""Writes the split-explainer top panel (1080x768) for project one v3: index.html + one scene per beat.
Times are on the v3 output timeline (edit_v3/raw.srt); each scene's own clock starts at its slot."""
import json
from pathlib import Path

HERE = Path(__file__).parent
W, H, TOTAL = 1080, 768, 88.69
# owner page (assets/brand.md)
# owner page from MP Studio → Brand (assets/brand.json in the repo; this file may be copied into work/<project>/panel/)
_BJ = next((b for d in HERE.resolve().parents for b in (d / "assets" / "brand.json", d / "mp-studio" / "assets" / "brand.json") if b.exists()), None)
_B = json.loads(_BJ.read_text(encoding="utf-8")) if _BJ else {}
HANDLE, BIO, AVATAR = _B.get("page", "your.page"), _B.get("bio", ""), "assets/avatar.png"  # from MP Studio → Brand
THEME = "dark"  # "light" = v3 split layout; "dark" = sits on the pop-out canvas (v4)
INK, BG = ("#EDEBE7", "#0E0E0E") if THEME == "dark" else ("#1d1b19", "#F4F2EE")

COMMON_CSS = """
@font-face { font-family: 'Vaz'; src: url('assets/fonts/Vazirmatn-Bold.ttf'); font-weight: 700; }
@font-face { font-family: 'Vaz'; src: url('assets/fonts/Vazirmatn-Regular.ttf'); font-weight: 400; }
#root { position: absolute; inset: 0; font-family: 'Vaz', Inter, sans-serif; direction: rtl; color: INK; }
.stage { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
.card { background: #fff; color: #1d1b19; border-radius: 26px; box-shadow: 0 16px 44px rgba(60,40,20,.12); padding: 28px 34px; }
.tag { display: inline-block; background: #D9520B; color: #fff; border-radius: 999px; padding: 6px 18px; font-size: 26px; font-weight: 700; }
.green { background: #15803D; }
.row { display: flex; align-items: center; gap: 18px; font-size: 32px; font-weight: 700; margin: 14px 0; }
.chk { width: 44px; height: 44px; border-radius: 50%; background: #E9E6E1; color: #fff; display: flex;
       align-items: center; justify-content: center; font-size: 26px; flex: none; }
.ico { width: 96px; height: 96px; border-radius: 24px; display: flex; align-items: center; justify-content: center;
       font-size: 50px; box-shadow: 0 10px 24px rgba(0,0,0,.12); }
.muted { color: #8a847c; font-weight: 400; }
.ig { background: radial-gradient(circle at 30% 107%, #fdf497 0%, #fdf497 5%, #fd5949 45%, #d6249f 60%, #285AEB 90%); }
.claude { background: #fff; }
"""

CLAUDE_SVG = ('<svg viewBox="0 0 100 100" width="62%" height="62%">' +
              "".join(f'<rect x="46" y="8" width="8" height="38" rx="4" fill="#D97757" transform="rotate({a} 50 50)"/>'
                      for a in range(0, 360, 30)) + "</svg>")
IG_GLYPH = ('<svg viewBox="0 0 100 100" width="62%" height="62%"><rect x="12" y="12" width="76" height="76" rx="22" '
            'fill="none" stroke="#fff" stroke-width="9"/><circle cx="50" cy="50" r="17" fill="none" stroke="#fff" '
            'stroke-width="9"/><circle cx="72" cy="28" r="6" fill="#fff"/></svg>')


def pop(sel, t, y=26, dur=0.32, scale=0.94):
    return (f'tl.fromTo("{sel}", {{opacity: 0, y: {y}, scale: {scale}}}, '
            f'{{opacity: 1, y: 0, scale: 1, duration: {dur}, ease: "back.out(1.7)"}}, {t});')


def tick(sel, t):  # check circle turns green with a pop
    return (f'tl.fromTo("{sel}", {{backgroundColor: "#E9E6E1", scale: 0.6}}, '
            f'{{backgroundColor: "#15803D", scale: 1, duration: 0.25, ease: "back.out(2.5)"}}, {t});')


COMMON_CSS = COMMON_CSS.replace("INK", INK)
BG_CSS = ("radial-gradient(rgba(255,255,255,.09) 1.5px, transparent 1.6px) 0 0/26px 26px, "
          "radial-gradient(circle at 50% 55%, rgba(255,140,60,.10), rgba(255,140,60,0) 50%), #0E0E0E") if THEME == "dark" else (
          "radial-gradient(circle at 50% 55%, rgba(255,140,60,.16), rgba(255,140,60,0) 45%), "
          "repeating-linear-gradient(0deg, rgba(0,0,0,.035) 0 1px, transparent 1px 48px), "
          "repeating-linear-gradient(90deg, rgba(0,0,0,.035) 0 1px, transparent 1px 48px), #F4F2EE")

SCENES = []


def scene(sid, start, end, html, js, css=""):
    SCENES.append((sid, start, end))
    dur = round(end - start, 3)
    out = f"""<template>
  <style>{COMMON_CSS}{css}</style>
  <div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
    <div id="{sid}-wrap" class="stage">{html}</div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#{sid}-wrap", {{opacity: {0 if sid != "s1" else 1}}}, {{opacity: 1, duration: 0.15}}, 0);
    {chr(10).join('    ' + j for j in js)}
    tl.to("#{sid}-wrap", {{opacity: 0, duration: 0.15}}, {max(dur - 0.17, 0.2)});
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""
    (HERE / "compositions" / f"{sid}.html").write_text(out, encoding="utf-8")


# 1. Claude ↔ Instagram, "new stage"
scene("s1", 0.0, 4.8,
      f'''<div style="display:flex;align-items:center;gap:90px">
        <div id="s1-ig" class="ico ig" style="width:170px;height:170px;border-radius:44px">{IG_GLYPH}</div>
        <div id="s1-line" style="width:170px;height:8px;border-radius:4px;background:repeating-linear-gradient(90deg,#FF7A3D 0 18px,transparent 18px 30px)"></div>
        <div id="s1-cl" class="ico claude" style="width:170px;height:170px;border-radius:44px">{CLAUDE_SVG}</div>
      </div>
      <div id="s1-tag" class="tag" style="position:absolute;top:150px">مرحله‌ی جدید ✦</div>''',
      ['tl.set("#s1-cl", {opacity: 1}, 0);', pop("#s1-ig", 1.15),
       'tl.fromTo("#s1-line", {scaleX: 0}, {scaleX: 1, duration: 0.5, ease: "power2.out"}, 1.6);',
       pop("#s1-tag", 2.9)])

# 2. connected + tasks done for you
rows2 = [("انتشار ریل امروز", 3.4), ("کامنت روی ۸ پست", 3.75), ("پاسخ به ۱۲ کامنت جدید", 4.1)]
scene("s2", 4.8, 10.8,
      f'''<div style="display:flex;flex-direction:column;align-items:center;gap:26px">
        <div style="display:flex;align-items:center;gap:24px">
          <div class="ico ig" style="width:84px;height:84px;border-radius:22px">{IG_GLYPH}</div>
          <div id="s2-link" style="width:120px;height:6px;border-radius:3px;background:#22C55E"></div>
          <div id="s2-ok" class="chk green" style="background:#22C55E">✓</div>
          <div class="ico claude" style="width:84px;height:84px;border-radius:22px">{CLAUDE_SVG}</div>
        </div>
        <div id="s2-card" class="card" style="width:640px">
          <div class="tag green" style="margin-bottom:6px">امروز برات انجام شد</div>
          {"".join(f'<div class="row"><div id="s2-c{i}" class="chk">✓</div>{t}</div>' for i, (t, _) in enumerate(rows2))}
        </div></div>''',
      ['tl.fromTo("#s2-link", {scaleX: 0}, {scaleX: 1, duration: 0.4}, 1.5);', pop("#s2-ok", 1.84),
       pop("#s2-card", 2.7)] + [tick(f"#s2-c{i}", t) for i, (_, t) in enumerate(rows2)])

# 3. app card + free badge
scene("s3", 10.8, 15.5,
      f'''<div id="s3-card" class="card" style="display:flex;align-items:center;gap:30px;width:720px;direction:ltr">
        <div class="ico claude" style="width:120px;height:120px">{CLAUDE_SVG}</div>
        <div><div style="font-family:Inter;font-size:46px;font-weight:700">Instagram Agent Skill</div>
        <div class="muted" style="font-family:Inter;font-size:26px">Claude · manages your page</div></div></div>
      <div id="s3-free" class="tag green" style="position:absolute;top:500px;font-size:40px;padding:10px 30px">رایگان ★</div>''',
      [pop("#s3-card", 0.1), 'tl.to("#s3-card", {scale: 1.04, duration: 0.18, yoyo: true, repeat: 1}, 1.2);',
       pop("#s3-free", 3.34, y=40, scale=0.6)])

# 4. not one skill: grid of 11 with live counter
icons = [("✍️", "#FF8A4C", "نویسنده پست"), ("💬", "#38BDF8", "کامنت‌گذار"), ("↩️", "#34C77B", "مدیر پاسخ‌ها"),
         ("👤", "#A855F7", "بهینه‌ساز پروفایل"), ("📅", "#F5B82E", "برنامه‌ریز محتوا"), ("⚡", "#F04E5E", "موتور وایرال"),
         ("🎣", "#14B8A6", "سازنده هوک"), ("🎬", "#6366F1", "سناریوی ریلز"), ("▦", "#EC4899", "چیدمان گرید"),
         ("👁", "#475569", "ردیاب ترند"), ("🔄", "#22C55E", "چرخه تعامل")]
fa = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
grid = "".join(f'<div id="s4-i{i}" style="display:flex;flex-direction:column;align-items:center;gap:8px;width:170px">'
               f'<div class="ico" style="background:{c};width:92px;height:92px">{e}</div>'
               f'<div style="font-size:22px;font-weight:700">{n}</div></div>' for i, (e, c, n) in enumerate(icons))
counter = "".join(f'<span id="s4-n{i}" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">{str(i + 1).translate(fa)} مهارت</span>'
                  for i in range(11))
g0, step = 2.5, 0.083
js4 = [pop("#s4-one", 0.1), 'tl.to("#s4-one", {opacity: 0, scale: 0.8, duration: 0.2}, 2.3);', pop("#s4-tag", g0 - 0.1)]
for i in range(11):
    t = round(g0 + i * step, 3)
    js4.append(pop(f"#s4-i{i}", t, y=30, dur=0.26))
    js4.append(f'tl.set("#s4-n{i}", {{opacity: 1}}, {t});' + (f' tl.set("#s4-n{i - 1}", {{opacity: 0}}, {t});' if i else ""))
js4.append('tl.fromTo("#s4-grid", {scale: 1}, {scale: 1.03, duration: 0.2, yoyo: true, repeat: 1}, 5.5);')
scene("s4", 15.5, 22.9,
      f'''<div id="s4-one" class="card" style="position:absolute;font-size:44px">فقط یه اسکیل؟</div>
      <div id="s4-tag" class="tag" style="position:absolute;top:34px;width:190px;height:50px;padding:0">{counter}</div>
      <div id="s4-grid" style="display:flex;flex-wrap:wrap;width:720px;gap:18px 6px;justify-content:center;margin-top:60px">{grid}</div>''',
      js4, css="[id^=s4-n]{opacity:0}")

# 5. post writer
lines5 = ["هوک: ۹۰٪ پیج‌ها این اشتباه رو می‌کنن…", "۳ نکته که بازدید رو دو برابر می‌کنه", "کپشن + هشتگ آماده ✓"]
scene("s5", 22.9, 28.2,
      f'''<div id="s5-card" class="card" style="width:700px">
        <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-size:36px;font-weight:700">پست جدید</div>
        <div id="s5-tag" class="tag">۲۱ فرمول تست‌شده ★</div></div>
        {"".join(f'<div id="s5-l{i}" class="row" style="font-size:30px;background:#F6F3EF;border-radius:14px;padding:12px 18px">{t}</div>' for i, t in enumerate(lines5))}
      </div>''',
      [pop("#s5-card", 0.1), pop("#s5-tag", 1.14, scale=0.6)] +
      [f'tl.fromTo("#s5-l{i}", {{clipPath: "inset(0 0 0 100%)"}}, {{clipPath: "inset(0 0 0 0%)", duration: 0.5, ease: "none"}}, {2.4 + i * 0.7});' for i in range(3)])

# 6. comments under others' posts
scene("s6", 28.2, 31.2,
      '''<div id="s6-card" class="card" style="width:640px">
        <div style="display:flex;align-items:center;gap:16px"><div style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#F5B82E,#F04E5E)"></div>
        <div style="font-family:Inter;font-size:28px;font-weight:700;direction:ltr">sara.design</div></div>
        <div style="height:150px;border-radius:18px;margin:16px 0;background:linear-gradient(135deg,#FFD9C2,#FFC4D6)"></div>
        <div id="s6-c" class="row" style="font-size:28px;background:#F6F3EF;border-radius:999px;padding:12px 22px">محتوای عالی بود! نکته‌ی دومت خیلی کاربردی بود 👌</div>
      </div><div id="s6-h" style="position:absolute;top:300px;font-size:90px">❤️</div>''',
      [pop("#s6-card", 0.1), 'tl.fromTo("#s6-c", {clipPath: "inset(0 0 0 100%)"}, {clipPath: "inset(0 0 0 0%)", duration: 0.8, ease: "none"}, 1.0);',
       pop("#s6-h", 2.0, y=0, scale=0.3)])

# 7. reply manager
c7 = [("mehdi_k", "قیمتش چنده؟"), ("niloo.art", "از کجا شروع کنم؟"), ("ali.dev", "عالی بود 🔥")]
scene("s7", 31.2, 34.1,
      f'''<div id="s7-card" class="card" style="width:680px"><div style="font-size:34px;font-weight:700;margin-bottom:6px">پاسخ به کامنت‌ها</div>
      {"".join(f'<div class="row" style="justify-content:space-between"><div><span style="font-family:Inter;font-size:24px;direction:ltr" class="muted">{u}</span><div style="font-size:30px">{t}</div></div><div id="s7-c{i}" class="chk">↩</div></div>' for i, (u, t) in enumerate(c7))}
      </div>''',
      [pop("#s7-card", 0.1)] + [tick(f"#s7-c{i}", 0.9 + i * 0.45) for i in range(3)])

# 8. profile optimiser
scene("s8", 34.1, 37.4,
      '''<div id="s8-card" class="card" style="width:700px;display:flex;align-items:center;gap:34px">
        <div style="position:relative;width:170px;height:170px;flex:none">
          <svg viewBox="0 0 100 100" width="170" height="170"><circle cx="50" cy="50" r="42" stroke="#EEE" stroke-width="10" fill="none"/>
          <circle id="s8-ring" cx="50" cy="50" r="42" stroke="#22C55E" stroke-width="10" fill="none" stroke-linecap="round"
            stroke-dasharray="264" stroke-dashoffset="100" transform="rotate(-90 50 50)"/></svg>
          <div id="s8-score" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:46px;font-weight:700">۶۲</div>
          <div id="s8-score2" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:46px;font-weight:700;opacity:0">۹۴</div></div>
        <div><div style="font-family:Inter;font-size:34px;font-weight:700;direction:ltr;text-align:right">''' + HANDLE + '''</div>
          <div class="muted" style="font-size:26px">بیو · هایلایت · لینک</div>
          <div style="display:flex;gap:10px;margin-top:14px"><span id="s8-b1" class="tag green">بیو بهینه شد</span><span id="s8-b2" class="tag green">هایلایت‌ها ✓</span></div></div>
      </div>''',
      [pop("#s8-card", 0.1), 'tl.fromTo("#s8-ring", {attr: {"stroke-dashoffset": 100}}, {attr: {"stroke-dashoffset": 16}, duration: 0.8, ease: "power2.out"}, 1.8);',
       'tl.to("#s8-score", {opacity: 0, duration: 0.1}, 2.2);', 'tl.to("#s8-score2", {opacity: 1, duration: 0.1}, 2.2);',
       pop("#s8-b1", 1.9, scale=0.6), pop("#s8-b2", 2.2, scale=0.6)])

# 9. weekly calendar
days = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
cols = ["#FF8A4C", "#38BDF8", "#A855F7", "#34C77B", "#F5B82E", "#EC4899", "#6366F1"]
scene("s9", 37.4, 40.1,
      f'''<div id="s9-card" class="card" style="width:820px"><div style="font-size:34px;font-weight:700;margin-bottom:14px">برنامه‌ی محتوایی این هفته</div>
      <div style="display:flex;gap:14px;justify-content:space-between">
      {"".join(f'<div style="display:flex;flex-direction:column;align-items:center;gap:10px"><div class="muted" style="font-size:26px">{d}</div><div id="s9-t{i}" style="width:88px;height:130px;border-radius:16px;background:{cols[i]}"></div></div>' for i, d in enumerate(days))}
      </div></div>''',
      [pop("#s9-card", 0.1)] + [pop(f"#s9-t{i}", round(0.6 + i * 0.12, 2), y=40, dur=0.28) for i in range(7)])

# 10. what / when / who
q10 = [("چی منتشر کنی؟", "✎", 2.72), ("چه زمانی منتشر کنی؟", "⏰", 4.5), ("با چه افرادی تعامل داشته باشی؟", "🤝", 5.36)]
scene("s10", 40.1, 48.1,
      '<div id="s10-h" class="card row" style="position:absolute;top:300px;font-size:40px;margin:0">🤝 یه اسکیل دیگه: دستیار انتشار</div>' + "".join(f'<div id="s10-q{i}" class="card row" style="position:absolute;top:{150 + i * 150}px;width:720px;margin:0;justify-content:space-between">'
              f'<div style="display:flex;align-items:center;gap:18px"><div id="s10-c{i}" class="chk">✓</div>{t}</div><div style="font-size:40px">{e}</div></div>'
              for i, (t, e, _) in enumerate(q10)),
      [pop("#s10-h", 0.3), 'tl.to("#s10-h", {opacity: 0, y: -30, duration: 0.25}, 2.4);'] + [pop(f"#s10-q{i}", t) for i, (_, _, t) in enumerate(q10)] + [tick(f"#s10-c{i}", t + 0.45) for i, (_, _, t) in enumerate(q10)])

# 11. the viral skill
scene("s11", 48.1, 53.9,
      '''<div id="s11-card" class="card" style="width:760px;background:#1d1b19;color:#fff">
        <div style="display:flex;align-items:center;gap:20px"><div class="ico" style="background:#F04E5E">🔥</div>
        <div><div class="muted" style="font-size:26px;color:#bbb">عجیب‌ترین بخشش</div><div style="font-size:48px;font-weight:700">اسکیل وایرال شدن</div></div></div>
        <svg viewBox="0 0 700 170" width="690" height="170" style="margin-top:18px"><path id="s11-line" d="M0 160 C150 150 250 140 330 110 S520 40 690 8"
          stroke="#FFC400" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="820" stroke-dashoffset="820"/></svg>
      </div><div id="s11-chip" class="tag" style="position:absolute;top:60px;font-size:32px">پربازدیدترین ریلزها 🔎</div>''',
      [pop("#s11-card", 0.84, y=40), 'tl.fromTo("#s11-line", {attr: {"stroke-dashoffset": 820}}, {attr: {"stroke-dashoffset": 0}, duration: 1.4, ease: "power2.inOut"}, 2.4);',
       pop("#s11-chip", 4.94, scale=0.6), 'tl.to("#s11-card", {scale: 1.05, duration: 0.2, yoyo: true, repeat: 1}, 3.95);'])

# 12. top reels, analysed
grads = ["#FF8A4C,#F04E5E", "#38BDF8,#6366F1", "#F5B82E,#FF8A4C", "#A855F7,#EC4899", "#34C77B,#14B8A6", "#475569,#1e293b"]
views = ["۲.۴M", "۸۹۰K", "۱.۱M", "۳.۲M", "۶۵۰K", "۴۲۰K"]
top = {0, 2, 3}
reels = "".join(f'<div id="s12-r{i}" style="position:relative;width:150px;height:230px;border-radius:18px;background:linear-gradient(160deg,{grads[i]});'
                f'box-shadow:0 10px 24px rgba(0,0,0,.15)"><div style="position:absolute;bottom:10px;right:12px;color:#fff;font-size:24px;font-weight:700">▶ {views[i]}</div>'
                + (f'<div id="s12-t{i}" class="tag" style="position:absolute;top:-14px;left:-10px;font-size:20px;padding:2px 12px">TOP</div>' if i in top else "")
                + "</div>" for i in range(6))
scene("s12", 53.9, 58.9,
      f'''<div style="display:flex;gap:16px;margin-top:-40px">{reels}</div>
      <div id="s12-mag" style="position:absolute;top:220px;left:330px;font-size:120px">🔍</div>
      <div id="s12-chip" class="card" style="position:absolute;bottom:88px;font-size:32px;padding:14px 28px">⚡ هوک قوی در ۳ ثانیه‌ی اول</div>''',
      [pop(f"#s12-r{i}", round(0.1 + i * 0.08, 2), y=40, dur=0.28) for i in range(6)] +
      [pop(f"#s12-t{i}", 0.9 + k * 0.15, scale=0.4) for k, i in enumerate(sorted(top))] +
      [pop("#s12-mag", 2.6, y=0, scale=0.4), 'tl.to("#s12-mag", {x: 380, duration: 1.0, ease: "power1.inOut"}, 2.9);',
       pop("#s12-chip", 3.4)])

# 13. reel → your own scenario
scene("s13", 58.9, 63.6,
      '''<div style="display:flex;align-items:center;gap:40px">
        <div id="s13-card" class="card" style="width:500px"><div style="font-size:34px;font-weight:700;margin-bottom:8px">سناریوی اختصاصی تو</div>
          <div id="s13-a" class="row"><div id="s13-c0" class="chk">✓</div>هوک: سؤال از دردِ مخاطب</div>
          <div id="s13-b" class="row"><div id="s13-c1" class="chk">✓</div>۳ ارزش با مثال</div>
          <div id="s13-c" class="row"><div id="s13-c2" class="chk">✓</div>دعوت به کامنت</div></div>
        <div id="s13-arrow" style="font-size:80px;color:#FF7A3D">⟵</div>
        <div id="s13-reel" style="width:150px;height:230px;border-radius:18px;background:linear-gradient(160deg,#FF8A4C,#F04E5E);box-shadow:0 10px 24px rgba(0,0,0,.15)"></div>
      </div>''',
      [pop("#s13-reel", 0.1), pop("#s13-arrow", 0.9, y=0), pop("#s13-card", 1.6)] + [tick(f"#s13-c{i}", 2.3 + i * 0.4) for i in range(3)])

# 14a. "every day, hours of thinking?" → not needed
scene("s14", 63.6, 66.6,
      '''<div style="display:flex;align-items:center;gap:30px">
        <div id="s14-g" style="font-size:150px">⏳</div>
        <div id="s14-q" class="card" style="position:relative;font-size:44px;font-weight:700;width:560px">هر روز ساعت‌ها فکر برای محتوا؟
          <div id="s14-x" style="position:absolute;left:20px;right:20px;top:50%;height:8px;border-radius:4px;background:#F04E5E"></div></div></div>
      <div id="s14-ok" class="tag green" style="position:absolute;top:560px;font-size:40px;padding:10px 30px">لازم نیست ✓</div>''',
      [pop("#s14-g", 0.1, y=0, scale=0.5), 'tl.fromTo("#s14-g", {rotation: 0}, {rotation: 180, duration: 0.6, ease: "power2.inOut"}, 0.7);',
       pop("#s14-q", 0.3), 'tl.fromTo("#s14-x", {scaleX: 0}, {scaleX: 1, duration: 0.35, ease: "power2.out"}, 1.5);',
       pop("#s14-ok", 1.75, scale=0.5)])

# 14b. the two questions you no longer have to answer
scene("s14b", 66.6, 70.0,
      '''<div id="s14b-a" class="card" style="position:absolute;top:150px;right:150px;font-size:40px;font-weight:700;border-radius:40px 40px 40px 8px">چه محتوایی بسازی؟ 🤔</div>
      <div id="s14b-b" class="card" style="position:absolute;top:330px;left:150px;font-size:40px;font-weight:700;border-radius:40px 40px 8px 40px">چه سناریویی بگیری؟ 🎬</div>
      <div id="s14b-ok" class="tag green" style="position:absolute;top:540px;font-size:36px;padding:10px 30px">آماده‌ست، برای تو ✓</div>''',
      [pop("#s14b-a", 0.68), pop("#s14b-b", 2.06), pop("#s14b-ok", 2.85, scale=0.5)])

# 14c. scenario cards tuned to your tone, niche and audience
cards14 = [("هوک", "#FF8A4C", -8), ("محتوا", "#38BDF8", 0), ("CTA", "#34C77B", 8)]
chips14 = [("لحن خودت", 2.74), ("حوزه‌ی کاری تو", 4.02), ("مخاطب پیجت", 5.44)]
scene("s14c", 70.0, 77.6,
      f'''<div style="display:flex;gap:26px;margin-top:-40px">
      {"".join(f'<div id="s14c-k{i}" class="card" style="width:250px;height:300px;padding:22px"><div class="tag" style="background:{c}">{t}</div>'
               f'<div style="margin-top:20px;display:flex;flex-direction:column;gap:14px">' + "".join('<div style="height:16px;border-radius:8px;background:#EEE9E3"></div>' for _ in range(4)) + "</div></div>"
               for i, (t, c, _) in enumerate(cards14))}
      </div>
      <div style="position:absolute;bottom:80px;display:flex;gap:16px">
      {"".join(f'<div id="s14c-h{i}" class="tag" style="font-size:30px">{t} ✓</div>' for i, (t, _) in enumerate(chips14))}</div>''',
      [f'tl.fromTo("#s14c-k{i}", {{opacity: 0, y: 60, rotation: 0}}, {{opacity: 1, y: 0, rotation: {r}, duration: 0.4, ease: "back.out(1.6)"}}, {0.05 + i * 0.15});'
       for i, (_, _, r) in enumerate(cards14)] + [pop(f"#s14c-h{i}", t, scale=0.6) for i, (_, t) in enumerate(chips14)] +
      ['tl.to("[id^=s14c-k]", {y: -12, duration: 0.25, yoyo: true, repeat: 1, stagger: 0.08}, 6.6);'])

# 15. Claude chat: send the link
scene("s15", 77.6, 82.4,
      f'''<div id="s15-card" class="card" style="width:820px;background:#262624;color:#eee;direction:ltr">
        <div style="display:flex;align-items:center;gap:14px;font-family:Inter;font-size:30px;font-weight:700">
          <div class="ico claude" style="width:56px;height:56px;border-radius:14px">{CLAUDE_SVG}</div>Claude</div>
        <div class="muted" style="font-family:Inter;font-size:28px;color:#aaa;margin:22px 0 14px">What shall we create?</div>
        <div style="display:flex;align-items:center;gap:14px;background:#30302e;border-radius:18px;padding:18px 20px">
          <div id="s15-link" style="flex:1;font-family:Inter;font-size:28px;color:#8AB4F8;white-space:nowrap;overflow:hidden">https://github.com/…/instagram-agent-skill</div>
          <div id="s15-send" style="width:54px;height:54px;border-radius:14px;background:#D97757;display:flex;align-items:center;justify-content:center;font-size:30px;color:#fff">↑</div>
        </div></div>''',
      [pop("#s15-card", 0.1), 'tl.fromTo("#s15-link", {clipPath: "inset(0 100% 0 0)"}, {clipPath: "inset(0 0% 0 0)", duration: 0.9, ease: "none"}, 2.8);',
       'tl.fromTo("#s15-send", {scale: 1}, {scale: 1.25, duration: 0.15, yoyo: true, repeat: 1}, 4.1);'])

# 16. follow + comment keyword → sent
scene("s16", 82.4, TOTAL,
      '''<div id="s16-card" class="card" style="width:760px">
        <div style="display:flex;align-items:center;gap:22px"><img src="''' + AVATAR + '''" style="width:110px;height:110px;border-radius:50%;object-fit:cover;flex:none">
          <div style="flex:1"><div style="font-family:Inter;font-size:34px;font-weight:700;direction:ltr;text-align:right">''' + HANDLE + '''</div>
          <div class="muted" style="font-size:24px">''' + BIO + '''</div></div></div>
        <div style="position:relative;height:74px;margin-top:20px">
          <div id="s16-f1" style="position:absolute;inset:0;border-radius:16px;background:#3B82F6;color:#fff;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700">فالو</div>
          <div id="s16-f2" style="position:absolute;inset:0;border-radius:16px;background:#EEE9E3;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700;opacity:0">دنبال می‌کنی ✓</div></div>
        <div style="margin-top:16px;border:2px solid #EEE9E3;border-radius:999px;padding:12px 24px;font-size:30px;display:flex;justify-content:space-between">
          <span id="s16-kw" style="font-weight:700">اینستاگرام</span><span class="muted">کامنت…</span></div>
      </div><div id="s16-dm" class="tag green" style="position:absolute;top:40px;font-size:30px">برات فرستادم ✅</div>''',
      [pop("#s16-card", 0.1), 'tl.fromTo("#s16-f1", {scale: 1}, {scale: 0.94, duration: 0.1, yoyo: true, repeat: 1}, 2.5);',
       'tl.to("#s16-f1", {opacity: 0, duration: 0.12}, 2.7);', 'tl.to("#s16-f2", {opacity: 1, duration: 0.12}, 2.7);',
       'tl.fromTo("#s16-kw", {clipPath: "inset(0 0 0 100%)"}, {clipPath: "inset(0 0 0 0%)", duration: 0.5, ease: "none"}, 3.33);',
       pop("#s16-dm", 4.4, scale=0.6)])

hosts = "\n".join(
    f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" data-start="{s}" '
    f'data-duration="{round(e - s, 3)}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>'
    for sid, s, e in SCENES)
index = f"""<!doctype html>
<html lang="fa">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {BG}; }}
      #bg {{ position: absolute; inset: 0;
        background: {BG_CSS}; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
      <div id="bg" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" data-layout-ignore></div>
{hosts}
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
(HERE / "index.html").write_text(index, encoding="utf-8")
(HERE / "scenes.json").write_text(json.dumps(SCENES), encoding="utf-8")
print(f"theme {THEME}: wrote index.html + {len(SCENES)} scenes")
