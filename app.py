"""Daily Record: photo-verified daily tasks, streaks, and live pinches.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import db
import styles as ui

st.set_page_config(page_title="Daily Record", page_icon="✺", layout="wide", initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)
db.init_db()

EMOJIS = ["🔥", "⚡", "🦊", "🐺", "🦁", "🐼", "🐸", "🦄", "👾", "🤖", "🌙", "🌊", "🍀", "💎", "🚀", "🎯"]
COLORS = {"Ember": "#ff6b1a", "Violet": "#7b5cff", "Rose": "#ff4fa3", "Cyan": "#46e0ff", "Lime": "#c8ff4d", "Gold": "#ffc94d"}
QUICK_TASKS = [("💧", "Drink 3L water"), ("🏃", "30 min workout"), ("📚", "Read 20 pages"), ("🧘", "Meditate 10 min"), ("🥗", "Eat a clean meal"), ("🛏️", "Make the bed")]
NAV = ["Arena", "Today", "Tasks", "Crew"]


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
def current_user():
    uid = db.user_for_session(st.query_params.get("s"))
    return db.get_user(uid) if uid else None


def sign_in(user_id: int):
    st.query_params["s"] = db.start_session(user_id)


def sign_out():
    db.end_session(st.query_params.get("s"))
    st.query_params.clear()


def go(page: str):
    st.session_state.nav = page


me = current_user()
users = db.list_users()


# --------------------------------------------------------------------------- #
# Dialogs (opened from the main script so live fragments can't close them)
# --------------------------------------------------------------------------- #
@st.dialog("🤏 Pinch")
def pinch_dialog(target_id: int):
    target = db.get_user(target_id)
    tasks = db.tasks_on(target_id)
    done = db.checkins_on(target_id)
    st.markdown(
        f'<div class="who">{ui.avatar(target["emoji"], target["color"], "lg")}'
        f'<div><div class="name">{ui.esc(target["name"])}</div>'
        f'<div class="meta">They get it instantly and have to answer with a live photo.</div></div></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    open_tasks = [t for t in tasks if t["id"] not in done]
    options = [None] + [t["id"] for t in open_tasks]
    labels = {None: "Just checking in"} | {t["id"]: f'{t["emoji"]} {t["title"]}' for t in open_tasks}
    task_id = st.selectbox("About which task?", options, format_func=lambda x: labels[x])
    msg = st.text_input("Message (optional)", placeholder="Gym selfie or it didn't happen 👀", max_chars=140)
    if st.button("Send pinch", type="primary", width="stretch"):
        try:
            db.pinch(me["id"], target_id, task_id, msg)
        except ValueError as e:
            st.error(str(e))
        else:
            st.session_state.flash = f"Pinched {target['name']} 🤏"
            st.rerun()


@st.dialog("📸 Answer the pinch")
def answer_dialog(pinch_id: int):
    p = next((x for x in db.incoming_pinches(me["id"]) if x["id"] == pinch_id), None)
    if not p:
        st.info("This pinch was already handled.")
        return
    st.markdown(
        f"**{ui.esc(p['from_name'])}** wants proof"
        + (f" of **{ui.esc(p['task_title'])}**" if p["task_title"] else "")
        + (f": _“{ui.esc(p['message'])}”_" if p["message"] else "."),
    )
    if p["task_title"]:
        st.caption("This photo also checks that task off for today if it isn't done yet.")
    use_cam = st.toggle("Use camera", value=True)
    photo = st.camera_input("Live proof") if use_cam else st.file_uploader("Proof photo", type=["jpg", "jpeg", "png", "webp", "heic"])
    if st.button("Send proof", type="primary", width="stretch", disabled=photo is None):
        try:
            db.answer_pinch(pinch_id, me["id"], photo.getvalue())
        except ValueError as e:
            st.error(str(e))
        else:
            st.session_state.flash = "Proof sent ✅"
            st.rerun()


# --------------------------------------------------------------------------- #
# Live pinch inbox: polls every few seconds on every page
# --------------------------------------------------------------------------- #
@st.fragment(run_every=4)
def pinch_inbox(uid: int):
    pending = db.incoming_pinches(uid)
    toasted = st.session_state.setdefault("toasted", set())
    for p in pending:
        if p["id"] not in toasted:
            toasted.add(p["id"])
            st.toast(f"**{p['from_name']}** pinched you!", icon="🤏")
    for p in pending[:3]:
        what = f" about <b>{ui.esc(p['task_title'])}</b>" if p["task_title"] else ""
        note = f"<div style='color:#cfcfd6;font-size:14px;margin-top:2px'>“{ui.esc(p['message'])}”</div>" if p["message"] else ""
        st.markdown(
            f'<div class="pinch-banner"><div class="big">🤏</div><div style="flex:1">'
            f'<b>{ui.esc(p["from_name"])}</b> pinched you{what}. Prove you\'re on it.{note}</div></div>',
            unsafe_allow_html=True,
        )
        a, b, _ = st.columns([1.2, 1, 4])
        if a.button("📸 Send proof", key=f"ans{p['id']}", type="primary", width="stretch"):
            st.session_state.answering = p["id"]
            st.rerun()
        if b.button("Dismiss", key=f"dis{p['id']}", width="stretch"):
            db.dismiss_pinch(p["id"], uid)
            st.rerun(scope="fragment")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_arena():
    all_stats = {u["id"]: db.stats(u["id"]) for u in users}
    proofs_today = sum(s["done"] for s in all_stats.values())
    top = max((s["current"] for s in all_stats.values()), default=0)
    st.markdown(
        ui.hero([(str(len(users)), "in the crew"), (f"{top}d", "longest live streak"), (str(proofs_today), "proofs today")]),
        unsafe_allow_html=True,
    )
    if not users:
        st.markdown(ui.empty("✺", "Nobody's here yet. Create the first profile."), unsafe_allow_html=True)
        st.button("Create a profile →", type="primary", on_click=go, args=("Crew",))
        return
    leaderboard()
    proofs = db.recent_proofs(12)
    st.markdown(ui.section("Proof wall", "Latest receipts from the crew", "Proof"), unsafe_allow_html=True)
    if proofs:
        st.markdown(ui.proof_wall(proofs, db.photo_path), unsafe_allow_html=True)
    else:
        st.markdown(ui.empty("📸", "No proofs yet. First photo sets the tone."), unsafe_allow_html=True)


@st.fragment(run_every=6)
def leaderboard():
    ranked = sorted(
        ((u, db.stats(u["id"])) for u in db.list_users()),
        key=lambda x: (-x[1]["current"], -x[1]["best"], -(x[1]["done"] / x[1]["total"] if x[1]["total"] else 0)),
    )
    st.markdown(ui.section("Competition", "Streak = consecutive days with every task proven · live", "Competition"), unsafe_allow_html=True)
    for i, (u, s) in enumerate(ranked, 1):
        row, btn = st.columns([8, 1.3], vertical_alignment="center")
        row.markdown(ui.leaderboard_row(i, u, s, db.last_7(u["id"])), unsafe_allow_html=True)
        if me and u["id"] != me["id"]:
            if btn.button("🤏 Pinch", key=f"pinch{u['id']}", width="stretch"):
                st.session_state.pinching = u["id"]
                st.rerun()
        elif me:
            btn.markdown("<div style='text-align:center;color:#9a9aa6;font-size:13px'>That's you</div>", unsafe_allow_html=True)
    if me:
        sent = db.sent_pinches(me["id"])
        if sent:
            st.markdown(ui.section("Your pinches", "Updates live when they answer"), unsafe_allow_html=True)
            for p in sent:
                left, right = st.columns([5, 1], vertical_alignment="center")
                what = f" · {ui.esc(p['task_title'])}" if p["task_title"] else ""
                left.markdown(
                    f'<div class="sent"><div class="who">{ui.avatar(p["to_emoji"], p["to_color"], "xs")}'
                    f'<span>{ui.esc(p["to_name"])}{what}</span></div>'
                    f'<span class="status {p["status"]}">{p["status"]}</span></div>',
                    unsafe_allow_html=True,
                )
                if p["thumb"]:
                    right.image(str(db.photo_path(p["thumb"])), width="stretch")


def need_login():
    st.markdown(ui.empty("🔒", "Sign in to see your day."), unsafe_allow_html=True)
    st.button("Go to Crew →", type="primary", on_click=go, args=("Crew",))


def page_today():
    if not me:
        return need_login()
    tasks = db.tasks_on(me["id"])
    done = db.checkins_on(me["id"])
    s = db.stats(me["id"])
    st.markdown(
        ui.section(f"{db.today():%A}, {db.today():%b %d}", f"{s['done']}/{s['total']} proven · {s['current']}🔥 streak", ""),
        unsafe_allow_html=True,
    )
    if not tasks:
        st.markdown(ui.empty("✦", "No daily tasks yet. Add a few and the streak starts."), unsafe_allow_html=True)
        st.button("Add tasks →", type="primary", on_click=go, args=("Tasks",))
        return
    st.progress(s["done"] / s["total"] if s["total"] else 0)
    st.write("")
    cols = st.columns(2, gap="medium")
    for i, t in enumerate(tasks):
        with cols[i % 2]:
            task_card(t, done.get(t["id"]))


def task_card(t, checkin):
    tid = t["id"]
    key = f"card-done-{tid}" if checkin else f"card-{tid}"
    with st.container(key=key):
        state = '<div class="task-state done">✓ Proven today</div>' if checkin else '<div class="task-state">Waiting for a photo</div>'
        st.markdown(
            f'<div class="task-head"><div class="task-emoji">{ui.esc(t["emoji"])}</div>'
            f'<div><div class="task-title">{ui.esc(t["title"])}</div>{state}</div></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        if checkin:
            st.markdown(
                f'<div class="proof"><img src="{ui.img_src(db.photo_path(checkin["thumb"]))}"/>'
                f'<span class="stamp pill dark">✓ {checkin["created_at"][11:16]}</span></div>',
                unsafe_allow_html=True,
            )
            with st.expander("Retake photo"):
                new = st.file_uploader("New photo", type=["jpg", "jpeg", "png", "webp", "heic"], key=f"re{tid}")
                if new and st.button("Replace", key=f"rep{tid}"):
                    _check_in(tid, new)
            return

        use_cam = st.toggle("Use camera", key=f"cam{tid}")
        if use_cam:
            photo = st.camera_input("Snap proof", key=f"shot{tid}", label_visibility="collapsed")
        else:
            photo = st.file_uploader("Upload proof", type=["jpg", "jpeg", "png", "webp", "heic"], key=f"up{tid}", label_visibility="collapsed")
        if photo is not None and not use_cam:
            st.image(photo, width="stretch")
        checked = st.checkbox(
            "Mark as done",
            key=f"chk{tid}",
            disabled=photo is None,
            help=None if photo else "Upload a photo of you doing it first.",
        )
        if checked and photo is not None:
            _check_in(tid, photo)


def _check_in(tid: int, photo):
    try:
        db.check_in(me["id"], tid, photo.getvalue())
    except ValueError as e:
        st.error(str(e))
        return
    for k in (f"chk{tid}", f"up{tid}", f"shot{tid}", f"re{tid}"):
        st.session_state.pop(k, None)
    s = db.stats(me["id"])
    if s["total"] and s["done"] == s["total"]:
        st.session_state.celebrate = True
        st.session_state.flash = f"Day complete. Streak: {s['current']} 🔥"
    else:
        st.session_state.flash = "Proof locked in ✓"
    st.rerun()


def page_tasks():
    if not me:
        return need_login()
    st.markdown(ui.section("Daily tasks", "These repeat every day. Every one needs a photo to keep the streak.", "Daily"), unsafe_allow_html=True)
    with st.container(key="card-add"):
        with st.form("add_task", clear_on_submit=True, border=False):
            c1, c2, c3 = st.columns([1, 5, 1.4], vertical_alignment="bottom")
            emoji = c1.text_input("Icon", value="✦", max_chars=2)
            title = c2.text_input("Task", placeholder="e.g. 10k steps")
            if c3.form_submit_button("Add task", type="primary", width="stretch"):
                try:
                    db.add_task(me["id"], title, emoji)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        st.caption("Quick add")
        existing = {t["title"].lower() for t in db.active_tasks(me["id"])}
        qcols = st.columns(len(QUICK_TASKS))
        for col, (e, title) in zip(qcols, QUICK_TASKS):
            if col.button(f"{e} {title}", key=f"q{title}", disabled=title.lower() in existing, width="stretch"):
                db.add_task(me["id"], title, e)
                st.rerun()

    tasks = db.active_tasks(me["id"])
    st.write("")
    if not tasks:
        st.markdown(ui.empty("✦", "Nothing yet. Add your first daily task above."), unsafe_allow_html=True)
    for t in tasks:
        a, b = st.columns([8, 1.2], vertical_alignment="center")
        a.markdown(
            f'<div class="sent"><div class="task-head"><div class="task-emoji" style="width:38px;height:38px;font-size:18px">'
            f'{ui.esc(t["emoji"])}</div><b>{ui.esc(t["title"])}</b></div>'
            f'<span style="color:#9a9aa6;font-size:12px">since {t["created_on"]}</span></div>',
            unsafe_allow_html=True,
        )
        if b.button("Remove", key=f"rm{t['id']}", width="stretch"):
            db.archive_task(t["id"], me["id"])
            st.rerun()
    st.caption("Removing a task never erases past proof. It just stops counting from now on.")


def page_crew():
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(ui.section("Sign in", "Pick your profile"), unsafe_allow_html=True)
        with st.container(key="card-signin"):
            if me:
                st.markdown(
                    f'<div class="who">{ui.avatar(me["emoji"], me["color"], "lg")}<div><div class="name">'
                    f'{ui.esc(me["name"])}</div><div class="meta">Signed in</div></div></div>',
                    unsafe_allow_html=True,
                )
                st.write("")
                if st.button("Sign out", width="stretch"):
                    sign_out()
                    st.rerun()
            elif not users:
                st.markdown(ui.empty("👋", "No profiles yet. Create one →"), unsafe_allow_html=True)
            else:
                with st.form("signin", border=False):
                    uid = st.selectbox("Profile", [u["id"] for u in users],
                                       format_func=lambda i: next(f'{u["emoji"]} {u["name"]}' for u in users if u["id"] == i))
                    pin = st.text_input("PIN", type="password", max_chars=8)
                    if st.form_submit_button("Sign in", type="primary", width="stretch"):
                        if db.verify_pin(uid, pin):
                            sign_in(uid)
                            st.session_state.goto = "Today"
                            st.rerun()
                        else:
                            st.error("Wrong PIN.")
    with right:
        st.markdown(ui.section("New profile", "Each person gets their own tasks", "New"), unsafe_allow_html=True)
        with st.container(key="card-new"):
            with st.form("new_user", clear_on_submit=True, border=False):
                name = st.text_input("Name", max_chars=24)
                c1, c2 = st.columns(2)
                emoji = c1.selectbox("Avatar", EMOJIS)
                color = c2.selectbox("Color", list(COLORS))
                p1, p2 = st.columns(2)
                pin = p1.text_input("PIN (4–8 digits)", type="password", max_chars=8)
                pin2 = p2.text_input("Repeat PIN", type="password", max_chars=8)
                if st.form_submit_button("Create profile", type="primary", width="stretch"):
                    if pin != pin2:
                        st.error("PINs don't match.")
                    else:
                        try:
                            uid = db.create_user(name, pin, emoji, COLORS[color])
                        except ValueError as e:
                            st.error(str(e))
                        else:
                            sign_in(uid)
                            st.session_state.goto = "Tasks"
                            st.session_state.flash = f"Welcome, {name.strip()} {emoji}"
                            st.rerun()
    if users:
        st.markdown(ui.section("The crew", f"{len(users)} members"), unsafe_allow_html=True)
        chips = "".join(
            f'<span class="chip" style="margin:0 8px 8px 0">{ui.avatar(u["emoji"], u["color"])}{ui.esc(u["name"])}</span>'
            for u in users
        )
        st.markdown(f"<div style='display:flex;flex-wrap:wrap'>{chips}</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
if "nav" not in st.session_state:
    st.session_state.nav = "Arena" if users else "Crew"
if goto := st.session_state.pop("goto", None):
    st.session_state.nav = goto

brand, nav, who = st.columns([3, 4, 3], vertical_alignment="center")
brand.markdown(
    '<div class="brand"><div class="mark">✺</div>Daily Record <span class="badge">PROOF+</span></div>',
    unsafe_allow_html=True,
)
with nav:
    st.segmented_control("Navigate", NAV, key="nav", required=True, label_visibility="collapsed")
if me:
    who.markdown(
        f'<div style="display:flex;justify-content:flex-end"><span class="chip">'
        f'{ui.avatar(me["emoji"], me["color"])}{ui.esc(me["name"])}</span></div>',
        unsafe_allow_html=True,
    )
else:
    who.markdown('<div style="text-align:right;color:#9a9aa6;font-size:14px">Not signed in</div>', unsafe_allow_html=True)

if msg := st.session_state.pop("flash", None):
    st.toast(msg, icon="⚡")
if st.session_state.pop("celebrate", False):
    st.balloons()

if me:
    pinch_inbox(me["id"])
    if (pid := st.session_state.pop("answering", None)) is not None:
        answer_dialog(pid)
    if (tid := st.session_state.pop("pinching", None)) is not None:
        pinch_dialog(tid)

page = st.session_state.nav or "Arena"
{"Arena": page_arena, "Today": page_today, "Tasks": page_tasks, "Crew": page_crew}[page]()
