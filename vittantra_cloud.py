"""
One link for everything: owner sign-in and saving work from the online app.

On the laptop nothing changes: files are written locally and you push with git.
On Streamlit Community Cloud the disk is temporary, so when the owner is signed
in, every save is also committed to GitHub; the app then reloads with the work
kept. Visitors can explore everything but cannot save.

Settings live in Streamlit Cloud → app → Settings → Secrets (never in code):

    owner_password = "a long password only you know"
    github_token   = "github_pat_..."     # fine-grained token, this repo, Contents: read and write
    github_repo    = "Agunp1/AI-Financial-Analyst"
    github_branch  = "main"
"""

from __future__ import annotations

import base64
import hmac
from pathlib import Path
from typing import Optional

import requests
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
API = "https://api.github.com"


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:          # no secrets file at all (normal on the laptop)
        return default


def cloud_mode() -> bool:
    """True when an owner password is configured, i.e. the online app."""
    return bool(_secret("owner_password"))


def is_owner() -> bool:
    """On the laptop you are always the owner; online you must sign in."""
    return not cloud_mode() or bool(st.session_state.get("vt_owner"))


def password_matches(given: str, expected: str) -> bool:
    """Exact match, ignoring spaces copied around the password by accident."""
    given, expected = given.strip(), expected.strip()
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


def sign_in_box() -> None:
    """Sidebar control: sign in / sign out (shown only on the online app)."""
    if not cloud_mode():
        return
    if st.session_state.get("vt_owner"):
        st.caption("Signed in as owner · your work is saved to GitHub")
        if st.button("Sign out", key="vt-sign-out"):
            st.session_state["vt_owner"] = False
            st.rerun()
        return
    with st.expander("Owner sign-in"):
        password = st.text_input("Password", type="password", key="vt-password")
        if st.button("Sign in", key="vt-sign-in"):
            if password_matches(password, _secret("owner_password")):
                st.session_state["vt_owner"] = True
                st.session_state.pop("vt-password", None)
                st.rerun()
            st.error("Wrong password.")
        st.caption("Visitors can explore everything; only the owner can save work.")


def github_settings() -> Optional[dict]:
    token, repo = _secret("github_token"), _secret("github_repo")
    if not (token and repo):
        return None
    return {"token": token, "repo": repo, "branch": _secret("github_branch", "main")}


def commit_file(path: Path, message: str, settings: Optional[dict] = None, session=requests) -> str:
    """Create or update one file on GitHub through the contents API."""
    settings = settings or github_settings()
    if not settings:
        return "GitHub saving is not set up (see DEPLOY.md, 'Sign in and save online')."
    relative = Path(path).resolve().relative_to(BASE_DIR).as_posix()
    url = f"{API}/repos/{settings['repo']}/contents/{relative}"
    headers = {"Authorization": f"Bearer {settings['token']}", "Accept": "application/vnd.github+json"}
    current = session.get(url, headers=headers, params={"ref": settings["branch"]}, timeout=20)
    body = {"message": message, "branch": settings["branch"],
            "content": base64.b64encode(Path(path).read_bytes()).decode()}
    if current.status_code == 200:
        body["sha"] = current.json()["sha"]
    response = session.put(url, headers=headers, json=body, timeout=30)
    if response.status_code not in (200, 201):
        return f"Saved here, but GitHub refused the save ({response.status_code}). Check the token in Secrets."
    return ""


def persist(path: Path, message: str) -> None:
    """Call after writing a file. Online and signed in → commit it to GitHub."""
    if not (cloud_mode() and is_owner()):
        return
    problem = commit_file(Path(path), message)
    if problem:
        st.warning(problem)
    else:
        st.toast("Saved to GitHub")


def owner_only_note(action: str = "save") -> None:
    st.caption(f"Sign in as owner (sidebar) to {action}. Visitors can try everything without saving.")
