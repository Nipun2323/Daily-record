# ✺ Daily Record

Photo-verified daily tasks for you and your crew. No photo, no check.

- **Daily tasks per person.** Each profile has its own list that repeats every day.
- **Proof-gated check-off.** The "Mark as done" box stays locked until you upload (or snap) a photo.
- **Competition on the home page.** Live leaderboard ranked by current streak, with best streak, today's progress ring, and a 7-day history.
- **Live pinches.** Pinch anyone on the leaderboard. They get a toast and banner within ~4 seconds and have to answer with a live photo. If the pinch named a task, that photo also checks it off. You see their answer update on your screen.
- **Proof wall.** The latest photos from everyone.

## Run locally

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. On share.streamlit.io, create an app pointing to `app.py`.
3. Optional: in the app's **Secrets**, set your timezone so "today" rolls over at your midnight:
   ```toml
   APP_TIMEZONE = "Asia/Kolkata"
   ```
   Defaults to UTC.

> **Storage warning.** Data lives in SQLite at `data/` and photos on disk. Streamlit Community Cloud's disk is **not persistent**: a reboot or redeploy wipes users, streaks, and photos. Fine for trying it out; for real use, move storage to a hosted DB + bucket (e.g. Supabase). All storage code is isolated in `db.py`, so that's the only file to change.

## How streaks work

A day counts when **every** task active that day has a photo. Your streak is the run of consecutive complete days. Today being unfinished doesn't break it until the day ends. Removing a task stops it counting from then on; past proof stays.

## Files

| File | What it does |
|---|---|
| `app.py` | Pages, navigation, dialogs, live fragments |
| `db.py` | SQLite schema, users/PINs, tasks, check-ins, streaks, pinches, image processing |
| `styles.py` | All CSS and HTML card builders |
| `.streamlit/config.toml` | Dark theme, 25 MB upload limit |

## Limits worth knowing

- "Real time" is polling every 4–6 s via `st.fragment(run_every=...)`. Streamlit has no server push for app code, so this is as live as it gets without an external service.
- The app checks that a photo exists, not what it shows. Anyone can upload any picture. The pinch-with-camera flow is the honesty check.
- PINs are hashed (PBKDF2) but this is friend-group security, not bank security.
