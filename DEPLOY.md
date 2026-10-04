# Deploy Vittantra online (free)

Vittantra runs on **Streamlit Community Cloud**, which is free for public apps.
The online app shows the data committed to GitHub; you refresh it from your
own computer and push, and the app updates by itself.

## One-time setup (about 10 minutes)

1. **Make sure your latest work is on GitHub** (in VS Code's terminal):
   ```powershell
   git pull origin main
   ```
   ```powershell
   git push origin main
   ```
2. Open <https://share.streamlit.io> and **sign in with GitHub** (free).
3. Click **Create app** → **Deploy a public app from GitHub**.
4. Fill in:
   - Repository: `Agunp1/AI-Financial-Analyst`
   - Branch: `main`
   - Main file path: `vittantra_app.py`
   - App URL: choose a name, e.g. `vittantra`
5. Open **Advanced settings** → Python version **3.11** → **Deploy**.

The first start takes a few minutes while it installs `requirements.txt`.
You then get a link like `https://vittantra.streamlit.app` to share.

## Keeping it up to date

The online app cannot download market data itself (and does not need to). On
your computer:

```powershell
python run_vittantra.py
```
```powershell
git add -A
```
```powershell
git commit -m "Data refresh"
```
```powershell
git push origin main
```

Streamlit Cloud notices the push and reloads the app with the new data.

## Good to know

- **Secrets stay local.** `.env` (FRED key, SEC user agent) is git-ignored and
  is not needed online, because the app only reads committed CSV files. Never
  paste keys into the code.
- **The app is public.** Anyone with the link can see the committed data,
  including the Academy work record (`academy_progress.json`) and the
  fictional sample clients. Do not add real client data.
- **Changes made online are temporary.** Saving a client or an Academy task
  on the cloud app is lost when the app restarts; do your work locally and
  push it.
- **The copilot's local AI (Ollama) is not available online**; the copilot
  uses its evidence templates there, which work the same way.
- If the app ever shows "resource limits", reboot it from the Streamlit Cloud
  menu (⋮ → Reboot).

## Sign in and save online (use only the link)

With this set up you can work entirely at <https://vittantra.streamlit.app>:
visitors explore everything, and when **you** sign in, Academy work, saved
clients and what-if proposals are saved to GitHub, so they survive restarts.

**1. Make a GitHub token that can only touch this project**
1. Open <https://github.com/settings/personal-access-tokens/new>.
2. Token name `vittantra-app`; Expiration: 1 year.
3. Repository access → **Only select repositories** → `AI-Financial-Analyst`.
4. Permissions → Repository permissions → **Contents: Read and write**.
5. **Generate token** and copy it (it starts with `github_pat_`). Don't paste it anywhere else.

**2. Give the app your password and the token**
1. Open <https://share.streamlit.io>, click **⋮** next to `vittantra` → **Settings** → **Secrets**.
2. Paste this, with your own password and token, and click **Save**:
   ```toml
   owner_password = "choose-a-long-password"
   owner_name = "Arjun"                 # optional: how the app greets you
   github_token = "github_pat_paste_here"
   github_repo = "Agunp1/AI-Financial-Analyst"
   github_branch = "main"
   ```
3. Open the app → sidebar → **Sign in / create account** → username `owner` and your password.
   The sidebar says *Signed in as owner*.

Each save makes a small commit on GitHub; the app reloads for a moment and
your work is there. Signing out (or closing the browser) ends the session;
you'll need to sign in again next time.

**Secrets stay secret:** they live only in Streamlit Cloud, never in the code.
If the token ever leaks, delete it on GitHub and make a new one.

## Automatic data refresh (no laptop needed)

`.github/workflows/refresh-data.yml` runs the pipeline on GitHub's free
computers every weekday after the US close (and all US-listed stocks on
Saturdays), checks the governance and formula tests, and commits the new
CSVs; the online app then reloads with fresh data.

One-time setup: GitHub repo → **Settings → Secrets and variables → Actions →
New repository secret**, add:
- `FRED_API_KEY` — the same value as in your `.env`
- `SEC_USER_AGENT` — the same value as in your `.env` (e.g. `Your Name you@email.com`)

To refresh now: repo → **Actions → Refresh data → Run workflow**. If a run
fails, GitHub emails you and the app keeps the last good data.

## Accounts for friends

Anyone can open the sidebar → **Sign in / create account** → **Create account**,
choose a username and a password, and keep their own Academy progress
(`academy_progress/<username>.json`). Friends cannot change the client book or
the approval queue; only the owner can.

- Passwords are never stored: `users.json` keeps a random salt and a PBKDF2-SHA256
  fingerprint per account. The repository is public, so usernames and Academy work
  are public; people should not reuse a password they use elsewhere.
- Five wrong passwords lock sign-in for a minute in that browser session.
- To remove an account, delete its entry from `users.json` (and its progress file).
- A forgotten password cannot be recovered: delete the entry and the person signs up again.
