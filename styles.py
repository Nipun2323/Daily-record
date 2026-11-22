"""Visual layer: global CSS and small HTML builders."""
from __future__ import annotations

import base64
import html
from functools import lru_cache

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@500;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#08080a; --panel:#111114; --panel-2:#17171c; --line:rgba(255,255,255,.08);
  --text:#f5f5f7; --muted:#9a9aa6; --accent:#ff6b1a; --accent-2:#ffb15c;
  --violet:#7b5cff; --pink:#ff4fa3; --cyan:#46e0ff; --lime:#c8ff4d;
  --iris:linear-gradient(120deg,#46e0ff 0%,#7b5cff 35%,#ff4fa3 70%,#ffb15c 100%);
  --r-lg:28px; --r-md:20px;
}

html, body, [data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--text); }
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 600px at 85% -10%, rgba(123,92,255,.18), transparent 60%),
    radial-gradient(900px 500px at -10% 10%, rgba(255,107,26,.10), transparent 60%),
    var(--bg);
}
header[data-testid="stHeader"], .stAppHeader{ display:none !important; }
[data-testid="stMainBlockContainer"], .block-container{ max-width:1240px; padding-top:1.4rem; padding-bottom:5rem; }
html, body, p, div, span, label, input, textarea, button{ font-family:'Inter',system-ui,sans-serif; }
h1,h2,h3,h4,.display{ font-family:'Unbounded',sans-serif !important; letter-spacing:-.02em; }
#MainMenu, footer, [data-testid="stToolbar"] {visibility:hidden;}

/* ---------- top bar ---------- */
.topbar{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:6px; }
.brand{ display:flex; align-items:center; gap:12px; font-family:'Unbounded'; font-weight:700; font-size:20px; }
.brand .mark{ width:40px; height:40px; border-radius:50%; display:grid; place-items:center;
  background:radial-gradient(circle at 30% 30%, #ffb15c, #ff6b1a 55%, #c2410c); color:#111; font-size:22px;
  box-shadow:0 0 0 4px rgba(255,107,26,.15), 0 8px 30px rgba(255,107,26,.35); animation:spin 14s linear infinite; }
.badge{ font-family:'Inter'; font-size:11px; font-weight:700; letter-spacing:.08em; padding:4px 9px; border-radius:7px;
  background:#2a2a31; color:#e7e7ea; border:1px solid var(--line); }
.chip{ display:inline-flex; align-items:center; gap:10px; padding:6px 14px 6px 6px; border-radius:999px;
  background:var(--panel); border:1px solid var(--line); font-weight:600; font-size:14px; }
.avatar{ width:36px; height:36px; border-radius:50%; display:grid; place-items:center; font-size:18px; flex:none;
  box-shadow: inset 0 0 0 2px rgba(255,255,255,.15); }
.avatar.lg{ width:58px; height:58px; font-size:28px; }

/* ---------- hero ---------- */
.hero{ position:relative; overflow:hidden; border-radius:var(--r-lg); padding:56px 52px 44px; margin:10px 0 28px;
  background:linear-gradient(135deg,#5b46ff 0%,#8f5bff 40%,#c86bff 70%,#ff8fd0 100%); color:#0b0b0f;
  min-height:330px; isolation:isolate; }
.hero::after{ content:""; position:absolute; inset:0; z-index:-1;
  background:radial-gradient(600px 300px at 80% 120%, rgba(255,255,255,.35), transparent 60%); }
.hero .orb{ position:absolute; right:6%; top:50%; width:260px; height:260px; border-radius:50%; z-index:-1;
  transform:translateY(-50%);
  background:
    radial-gradient(circle at 32% 28%, rgba(255,255,255,.95) 0 6%, transparent 22%),
    conic-gradient(from 210deg, #46e0ff, #7b5cff, #ff4fa3, #ffb15c, #c8ff4d, #46e0ff);
  filter:saturate(1.2); box-shadow:0 40px 120px rgba(40,10,120,.55), inset -30px -40px 80px rgba(20,0,80,.45);
  animation:float 7s ease-in-out infinite; }
.hero .orb.small{ width:70px; height:70px; right:34%; top:18%; animation-duration:9s; opacity:.9; }
.hero .eyebrow{ display:flex; gap:8px; margin-bottom:22px; flex-wrap:wrap; }
.pill{ display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:999px; font-size:12px; font-weight:600;
  background:rgba(255,255,255,.75); color:#16161b; backdrop-filter:blur(6px); }
.pill.dark{ background:#0b0b0f; color:#fff; }
.hero h1{ font-size:clamp(34px,5.6vw,68px); line-height:1.02; margin:0; font-weight:800; color:#0b0b0f; max-width:720px; }
.hero h1 .tag{ display:inline-block; background:#0b0b0f; color:#fff; padding:0 .32em; border-radius:.35em; transform:rotate(-2deg); }
.hero p.lead{ max-width:520px; margin:18px 0 0; font-size:16px; line-height:1.55; color:#1c1530; font-weight:500; }
.hero .kpis{ display:flex; gap:12px; margin-top:28px; flex-wrap:wrap; }
.kpi{ background:rgba(11,11,15,.88); color:#fff; border-radius:18px; padding:14px 18px; min-width:132px; }
.kpi b{ font-family:'Unbounded'; font-size:26px; display:block; }
.kpi span{ font-size:12px; color:#b9b9c4; }

/* ---------- section heads ---------- */
.sec{ display:flex; align-items:end; justify-content:space-between; margin:34px 0 14px; }
.sec h2{ font-size:28px; margin:0; padding:0 !important; line-height:1.2; }
.sec{ gap:16px; flex-wrap:wrap; }
.sec .sub{ color:var(--muted); font-size:14px; }
.grad-text{ background:var(--iris); -webkit-background-clip:text; background-clip:text; color:transparent; }

/* ---------- leaderboard ---------- */
.lb{ position:relative; display:grid; grid-template-columns:84px 1fr auto auto; margin-bottom:6px; align-items:center; gap:18px;
  padding:18px 22px; border-radius:var(--r-md); background:var(--panel); border:1px solid var(--line);
  transition:transform .25s ease, border-color .25s ease; overflow:hidden; }
.lb:hover{ transform:translateY(-2px); border-color:rgba(255,255,255,.18); }
.lb.first{ background:linear-gradient(var(--panel),var(--panel)) padding-box, var(--iris) border-box; border:1.5px solid transparent; }
.lb.first::before{ content:""; position:absolute; inset:0; background:radial-gradient(500px 120px at 0% 0%, rgba(123,92,255,.25), transparent 70%); pointer-events:none; }
.rank{ font-family:'Unbounded'; font-weight:800; font-size:40px; white-space:nowrap; line-height:1; color:transparent; -webkit-text-stroke:1.5px rgba(255,255,255,.35); }
.lb.first .rank{ -webkit-text-stroke:0; background:var(--iris); -webkit-background-clip:text; background-clip:text; }
.who{ display:flex; align-items:center; gap:14px; min-width:0; }
.who .name{ font-weight:700; font-size:18px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.who .meta{ color:var(--muted); font-size:13px; margin-top:2px; }
.dots{ display:flex; gap:5px; margin-top:8px; }
.dot{ width:14px; height:14px; border-radius:4px; background:#24242b; }
.dot.on{ background:var(--accent); box-shadow:0 0 10px rgba(255,107,26,.5); }
.dot.none{ background:transparent; border:1px dashed #33333b; }
.streak{ text-align:right; }
.streak b{ font-family:'Unbounded'; font-size:38px; line-height:1; }
.streak span{ display:block; color:var(--muted); font-size:12px; margin-top:4px; }
.ring{ --p:0; width:58px; height:58px; border-radius:50%; display:grid; place-items:center;
  background:conic-gradient(var(--accent) calc(var(--p)*1%), #24242b 0); }
.ring i{ width:46px; height:46px; border-radius:50%; background:var(--panel); display:grid; place-items:center;
  font-style:normal; font-size:12px; font-weight:700; }

/* ---------- task cards ---------- */
.task-head{ display:flex; align-items:center; gap:14px; }
.task-emoji{ width:48px; height:48px; border-radius:14px; display:grid; place-items:center; font-size:24px;
  background:linear-gradient(135deg,#1f1f26,#2a2a33); border:1px solid var(--line); }
.task-title{ font-family:'Unbounded'; font-size:18px; font-weight:700; }
.task-state{ font-size:12px; color:var(--muted); margin-top:2px; }
.task-state.done{ color:var(--lime); }
.proof{ position:relative; border-radius:16px; overflow:hidden; aspect-ratio:16/10; background:#1a1a20; }
.proof img{ width:100%; height:100%; object-fit:cover; display:block; }
.proof .stamp{ position:absolute; left:10px; top:10px; }

/* ---------- proof wall ---------- */
.wall{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:18px; }
.shot .img{ position:relative; aspect-ratio:4/3; border-radius:18px; overflow:hidden; background:#16161b; }
.shot .img img{ width:100%; height:100%; object-fit:cover; transition:transform .5s ease; }
.shot:hover .img img{ transform:scale(1.06); }
.shot .img .ov{ position:absolute; inset:auto 0 0 0; padding:40px 14px 12px; color:#fff; font-weight:600; font-size:14px;
  background:linear-gradient(transparent, rgba(0,0,0,.75)); opacity:0; transition:opacity .3s; }
.shot:hover .ov{ opacity:1; }
.shot .by{ display:flex; align-items:center; justify-content:space-between; margin-top:10px; font-size:14px; }
.shot .by .l{ display:flex; align-items:center; gap:8px; font-weight:600; }
.shot .by .r{ color:var(--muted); font-size:12px; }
.avatar.xs{ width:24px; height:24px; font-size:12px; }

/* ---------- pinch ---------- */
.pinch-banner{ display:flex; align-items:center; gap:16px; padding:16px 20px; border-radius:var(--r-md);
  background:linear-gradient(90deg, rgba(255,107,26,.18), rgba(255,79,163,.12)); border:1px solid rgba(255,107,26,.45);
  animation:pulse 1.8s ease-in-out infinite; margin-bottom:10px; }
.pinch-banner .big{ font-size:30px; animation:wiggle 1.2s ease-in-out infinite; }
.pinch-banner b{ font-family:'Unbounded'; }
.sent{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 14px; border-radius:14px;
  background:var(--panel); border:1px solid var(--line); margin-bottom:8px; font-size:14px; }
.status{ font-size:11px; font-weight:700; letter-spacing:.06em; padding:3px 8px; border-radius:6px; text-transform:uppercase; }
.status.pending{ background:#2b2208; color:#ffcf5c; }
.status.answered{ background:#13280c; color:var(--lime); }
.status.dismissed{ background:#2a1414; color:#ff8a8a; }

/* ---------- empty state ---------- */
.empty{ text-align:center; padding:48px 20px; border:1px dashed #2c2c34; border-radius:var(--r-md); color:var(--muted); }
.empty .e{ font-size:40px; }

/* ---------- streamlit widget skin ---------- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button{
  border-radius:999px; font-weight:600; border:1px solid var(--line); background:var(--panel-2); color:var(--text);
  transition:all .2s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover{ border-color:var(--accent); color:#fff; transform:translateY(-1px); }
.stButton > button[kind*="rimary"], .stFormSubmitButton > button[kind*="rimary"]{
  background:linear-gradient(135deg,#ff8a3d,#ff6b1a); color:#111; border:none; box-shadow:0 8px 24px rgba(255,107,26,.35); }
.stButton > button[kind*="rimary"]:hover{ color:#000; box-shadow:0 10px 30px rgba(255,107,26,.55); }
[data-testid="stVerticalBlockBorderWrapper"]{ border-radius:var(--r-md) !important; }
div[class*="st-key-card"]{ background:var(--panel); border:1px solid var(--line); border-radius:var(--r-md); padding:20px; }
div[class*="st-key-card"]:hover{ border-color:rgba(255,255,255,.16); }
div[class*="st-key-card-done"]{ background:linear-gradient(var(--panel),var(--panel)) padding-box,
  linear-gradient(135deg,#c8ff4d,#46e0ff) border-box; border:1.5px solid transparent; }
[data-testid="stFileUploaderDropzone"]{ background:#0e0e12; border:1.5px dashed #34343d; border-radius:16px; }
[data-testid="stFileUploaderDropzone"]:hover{ border-color:var(--accent); }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-baseweb="select"] > div{
  background:#0e0e12 !important; border-radius:12px !important; }
[data-testid="stCheckbox"] label p{ font-weight:600; }
[data-testid="stButtonGroup"] button{ border-radius:999px !important; padding:6px 18px !important; font-weight:600; }
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"]{
  background:#f5f5f7 !important; color:#0b0b0f !important; }
[data-testid="stToast"]{ background:#17171c; border:1px solid rgba(255,107,26,.5); border-radius:16px; }
[data-testid="stDialog"] div[role="dialog"]{ background:#111114; border:1px solid var(--line); border-radius:24px; }

@keyframes float{ 0%,100%{ transform:translateY(-50%) rotate(0deg);} 50%{ transform:translateY(-56%) rotate(8deg);} }
@keyframes spin{ to{ transform:rotate(360deg);} }
@keyframes pulse{ 0%,100%{ box-shadow:0 0 0 0 rgba(255,107,26,.0);} 50%{ box-shadow:0 0 0 6px rgba(255,107,26,.12);} }
@keyframes wiggle{ 0%,100%{ transform:rotate(0);} 25%{ transform:rotate(-14deg);} 75%{ transform:rotate(14deg);} }
@media (max-width: 720px){
  .hero{ padding:34px 22px; } .hero .orb{ width:150px; height:150px; right:-30px; top:22%; opacity:.7; }
  .sec h2{ font-size:22px; } .sec .sub{ font-size:12px; }
  .lb{ grid-template-columns:48px 1fr auto; padding:14px; gap:10px; } .streak b{ font-size:28px; } .lb .ring{ display:none; } .rank{ font-size:28px; }
}
</style>
"""


def esc(s) -> str:
    return html.escape(str(s or ""))


@lru_cache(maxsize=256)
def img_src(name: str, loader) -> str:
    """Base64 data URI for a stored photo (names are immutable, so cache)."""
    data = loader(name) if name else b""
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}" if data else ""


def avatar(emoji: str, color: str, size: str = "") -> str:
    return (
        f'<div class="avatar {size}" style="background:radial-gradient(circle at 30% 30%, '
        f'{color}ee, {color}88);">{esc(emoji)}</div>'
    )


def hero(kpis: list[tuple[str, str]]) -> str:
    k = "".join(f'<div class="kpi"><b>{esc(v)}</b><span>{esc(lbl)}</span></div>' for v, lbl in kpis)
    return f"""
<div class="hero">
  <div class="orb"></div><div class="orb small"></div>
  <div class="eyebrow"><span class="pill dark">✺ Daily Record</span><span class="pill">Photo-verified</span><span class="pill">Live pinches</span></div>
  <h1>Show up. <span class="tag">Prove</span> it. Every day.</h1>
  <p class="lead">No photo, no check. Build streaks with your crew, and pinch anyone who looks like they're slacking.</p>
  <div class="kpis">{k}</div>
</div>"""


def section(title: str, sub: str = "", grad_word: str = "") -> str:
    t = esc(title)
    if grad_word:
        t = t.replace(esc(grad_word), f'<span class="grad-text">{esc(grad_word)}</span>')
    return f'<div class="sec"><h2>{t}</h2><div class="sub">{esc(sub)}</div></div>'


def leaderboard_row(rank: int, user, st_: dict, week: list) -> str:
    dots = "".join(
        f'<div class="dot {"on" if d else ("none" if d is None else "")}"></div>' for d in week
    )
    pct = round(100 * st_["done"] / st_["total"]) if st_["total"] else 0
    flame = "🔥" if st_["current"] else "·"
    return f"""
<div class="lb {'first' if rank == 1 else ''}">
  <div class="rank">{rank:02d}</div>
  <div class="who">{avatar(user['emoji'], user['color'], 'lg')}
    <div style="min-width:0"><div class="name">{esc(user['name'])}</div>
      <div class="meta">Best {st_['best']}d · {st_['done']}/{st_['total']} today</div>
      <div class="dots" title="Last 7 days">{dots}</div></div></div>
  <div class="ring" style="--p:{pct}"><i>{pct}%</i></div>
  <div class="streak"><b>{st_['current']}</b><span>{flame} day streak</span></div>
</div>"""


def proof_wall(rows, loader) -> str:
    cards = []
    for r in rows:
        src = img_src(r["thumb"], loader)
        cards.append(f"""
<div class="shot"><div class="img"><img src="{src}" alt="proof"/>
  <div class="ov">{esc(r['task_emoji'])} {esc(r['title'])}</div></div>
  <div class="by"><div class="l">{avatar(r['emoji'], r['color'], 'xs')}{esc(r['name'])}</div>
  <div class="r">{esc(r['day'])}</div></div></div>""")
    return f'<div class="wall">{"".join(cards)}</div>'


def empty(emoji: str, text: str) -> str:
    return f'<div class="empty"><div class="e">{emoji}</div><div>{esc(text)}</div></div>'
