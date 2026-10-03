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
