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

## Deploy for you and your friends (free)

Two free services: **Supabase** holds the data (users, streaks, photos), **Streamlit Community Cloud** runs the app. Without Supabase, Streamlit Cloud wipes everything whenever the app restarts.

### 1. Create the database (Supabase)
1. Sign up at supabase.com → **New project**. Pick a region near you and **save the database password**.
2. When the project is ready, click **Connect** (top of the dashboard).
3. Under connection string, choose **Session pooler** and copy the URI. It looks like:
   `postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
4. Replace `[YOUR-PASSWORD]` with your password.

Use the **Session pooler**, not "Direct connection": on the free plan the direct connection is IPv6-only, and Streamlit Cloud can't reach it. The app creates its tables on first run, so you don't need to set anything up in Supabase.

### 2. Deploy the app (Streamlit Community Cloud)
1. Merge this branch into `main` (or deploy straight from this branch).
2. Go to share.streamlit.io, sign in with GitHub, click **Create app** and pick this repo, the branch, and `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   DATABASE_URL = "postgresql://postgres.abcdefgh:YOURPASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
   APP_TIMEZONE = "Asia/Kolkata"   # your timezone; "today" resets at this midnight
   ```
4. Deploy. On the **Crew** page you should see "🟢 Storage: cloud database". If it says 🟠, the secret isn't set.

### 3. Use it together
- Send your friend the app URL. Each of you creates a profile on **Crew** with your own PIN.
- Signing in puts a session token in the URL. Bookmark that link (or add it to your home screen) to stay signed in on that device.
- The **Arena** home page shows both streaks live. Hit 🤏 Pinch on your friend's row to make them send a live photo.

### Good to know
- **Streamlit Cloud apps sleep** after a period with no visitors. The first visit then shows a "wake up" button and takes ~30 s. Your data is safe in Supabase.
- **Supabase free projects pause** after about a week with no activity. Using the app daily keeps it awake; if it does pause, click Restore in the Supabase dashboard.
- **Who can see it:** Streamlit Cloud apps are public by default, so anyone with the link can see the leaderboard and proof wall. To restrict it, use the app's **Settings → Sharing** on Streamlit Cloud.
- **Space:** photos are compressed (~150 KB full, ~25 KB thumbnail). Supabase's free 500 MB fits a few thousand check-ins.
- If a password contains special characters (`@`, `#`, `/`, `:`), URL-encode them in `DATABASE_URL` (e.g. `@` → `%40`), or reset it to letters and numbers.

## How streaks work

A day counts when **every** task active that day has a photo. Your streak is the run of consecutive complete days. Today being unfinished doesn't break it until the day ends. Removing a task stops it counting from then on; past proof stays.

## Files

| File | What it does |
|---|---|
| `app.py` | Pages, navigation, dialogs, live fragments |
| `db.py` | Storage (Postgres if `DATABASE_URL` is set, else local SQLite), users/PINs, tasks, check-ins, streaks, pinches, photos |
| `styles.py` | All CSS and HTML card builders |
| `.streamlit/config.toml` | Dark theme, 25 MB upload limit |
| `.streamlit/secrets.toml.example` | Template for the secrets above |

## Limits worth knowing

- "Real time" is polling every 4–6 s via `st.fragment(run_every=...)`. Streamlit has no server push for app code, so this is as live as it gets without an external service.
- The app checks that a photo exists, not what it shows. Anyone can upload any picture. The pinch-with-camera flow is the honesty check.
- PINs are hashed (PBKDF2) but this is friend-group security, not bank security.
