"""
One link for everything: owner sign-in and saving work from the online app.

On the laptop nothing changes: files are written locally and you push with git.
On Streamlit Community Cloud the disk is temporary, so saves are committed to
GitHub; the app then reloads with the work kept. Visitors can explore
everything. Anyone can create an account (vittantra_accounts.py) and keep their
own Academy progress; only the owner can change shared data (client book,
approval queue).

Settings live in Streamlit Cloud → app → Settings → Secrets (never in code):

    owner_password = "a long password only you know"
    github_token   = "github_pat_..."     # fine-grained token, this repo, Contents: read and write
    github_repo    = "Agunp1/AI-Financial-Analyst"
    github_branch  = "main"
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from pathlib import Path
from typing import Optional

import requests
import streamlit as st

import vittantra_accounts as accounts


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


def current_user() -> Optional[str]:
    """'owner', a signed-in username, or None for a visitor."""
    if is_owner():
        return "owner"
    return st.session_state.get("vt_user")


def progress_path() -> Optional[Path]:
    """Where the signed-in person's Academy work record lives (None for visitors)."""
    user = current_user()
    if user is None:
        return None
    if user == "owner":
        from academy_desk import PROGRESS_FILE
        return PROGRESS_FILE
    return accounts.progress_file(user)


def _show_save_status() -> None:
    status = st.session_state.get("vt_save_status")
    if status:
        (st.success if status.startswith(("Saved", "Saving works")) else st.warning)(status)


def _sign_out() -> None:
    for key in ("vt_owner", "vt_user", "vt_save_status"):
        st.session_state.pop(key, None)
    st.rerun()


def _too_many_attempts() -> bool:
    until = st.session_state.get("vt_locked_until", 0)
    if time.time() < until:
        st.error(f"Too many attempts. Try again in {int(until - time.time()) + 1} seconds.")
        return True
    return False


def _failed_attempt() -> None:
    fails = st.session_state.get("vt_fails", 0) + 1
    st.session_state["vt_fails"] = fails
    if fails >= 5:
        st.session_state["vt_locked_until"] = time.time() + 60
        st.session_state["vt_fails"] = 0


def _latest_users() -> dict:
    """Accounts from GitHub when available (another session may have just added one), else local."""
    remote = fetch_file(accounts.USERS_FILE)
    if remote is not None:
        try:
            users = json.loads(remote)
            accounts.save_users(users)
            return users
        except ValueError:
            pass
    return accounts.load_users()


def sign_in_box() -> None:
    """Sidebar: sign in, create an account, sign out (shown only on the online app)."""
    if not cloud_mode():
        return
    if st.session_state.get("vt_owner"):
        st.caption("Signed in as owner · your work is saved to GitHub")
        _show_save_status()
        if st.button("Test saving", key="vt-test-save"):
            st.session_state["vt_save_status"] = check_github()
            st.rerun()
        if st.button("Sign out", key="vt-sign-out"):
            _sign_out()
        return
    user = st.session_state.get("vt_user")
    if user:
        st.caption(f"Signed in as **{user}** · your Academy work is saved")
        _show_save_status()
        if st.button("Sign out", key="vt-sign-out"):
            _sign_out()
        return
    with st.expander("Sign in / create account"):
        sign_in, create = st.tabs(["Sign in", "Create account"])
        with sign_in:
            name = st.text_input("Username", key="vt-username", placeholder="owner, or your username",
                                 help="The owner signs in with username 'owner' (or leaves it empty).")
            password = st.text_input("Password", type="password", key="vt-password")
            if st.button("Sign in", key="vt-sign-in") and not _too_many_attempts():
                if accounts.normalize(name) in ("owner", ""):
                    if password_matches(password, _secret("owner_password")):
                        st.session_state["vt_owner"] = True
                        st.rerun()
                else:
                    found = accounts.check_login(accounts.load_users(), name, password) or \
                        accounts.check_login(_latest_users(), name, password)
                    if found:
                        st.session_state["vt_user"] = found
                        st.rerun()
                _failed_attempt()
                st.error("Wrong username or password. Owner: username **owner** (or empty) and the password set "
                         "in Streamlit Secrets. Passwords are case-sensitive.")
        with create:
            new_name = st.text_input("Choose a username", key="vt-new-username",
                                     help="3–20 characters: letters, numbers, - or _. Usernames are public.")
            new_password = st.text_input("Choose a password", type="password", key="vt-new-password",
                                         help=f"At least {accounts.MIN_PASSWORD} characters.")
            repeat = st.text_input("Repeat the password", type="password", key="vt-new-password-2")
            st.caption("Don't reuse a password you use elsewhere. Passwords are never stored, only a scrambled "
                       "fingerprint, but usernames and Academy work are saved in Vittantra's public project.")
            if st.button("Create account", key="vt-create"):
                if st.session_state.get("vt_created"):
                    st.error("One new account per visit. Please sign in.")
                elif new_password != repeat:
                    st.error("The two passwords do not match.")
                else:
                    users, problem = accounts.add_user(_latest_users(), new_name, new_password)
                    if problem:
                        st.error(problem)
                    else:
                        accounts.save_users(users)
                        saved = commit_file(accounts.USERS_FILE, f"New Vittantra account: "
                                            f"{accounts.normalize(new_name)}") if github_settings() else ""
                        if saved:
                            st.error(f"Account not saved: {saved}")
                        else:
                            st.session_state["vt_created"] = True
                            st.session_state["vt_user"] = accounts.normalize(new_name)
                            st.rerun()
        st.caption("Visitors can explore everything. Sign in to keep your own Academy progress.")


def github_settings() -> Optional[dict]:
    token, repo = _secret("github_token"), _secret("github_repo")
    if not (token and repo):
        return None
    return {"token": token, "repo": repo, "branch": _secret("github_branch", "main")}


def check_github(settings: Optional[dict] = None, session=requests) -> str:
    """Plain-English check that the token can write to the repository."""
    settings = settings or github_settings()
    if not settings:
        return "GitHub saving is not set up: add github_token and github_repo in Secrets."
    headers = {"Authorization": f"Bearer {settings['token'].strip()}", "Accept": "application/vnd.github+json"}
    try:
        response = session.get(f"{API}/repos/{settings['repo'].strip()}", headers=headers, timeout=20)
    except Exception as error:
        return f"Could not reach GitHub ({type(error).__name__})."
    if response.status_code == 401:
        return "GitHub rejected the token (401): it is wrong, expired or was pasted with extra characters."
    if response.status_code == 404:
        return (f"GitHub cannot see {settings['repo']} with this token (404): give the token access to "
                "this repository (Repository access → Only select repositories).")
    if response.status_code != 200:
        return f"GitHub answered {response.status_code}."
    if not response.json().get("permissions", {}).get("push"):
        return "The token can read but not write: set Repository permissions → Contents → Read and write."
    return "Saving works: the token can write to the repository."


def fetch_file(path: Path, settings: Optional[dict] = None, session=requests) -> Optional[str]:
    """Current text of a repository file on GitHub, or None (not set up, missing or unreachable)."""
    settings = settings or github_settings()
    if not settings:
        return None
    relative = Path(path).resolve().relative_to(BASE_DIR).as_posix()
    headers = {"Authorization": f"Bearer {settings['token'].strip()}", "Accept": "application/vnd.github+json"}
    try:
        response = session.get(f"{API}/repos/{settings['repo'].strip()}/contents/{relative}", headers=headers,
                               params={"ref": settings["branch"]}, timeout=20)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    return base64.b64decode(response.json()["content"]).decode()


def commit_file(path: Path, message: str, settings: Optional[dict] = None, session=requests) -> str:
    """Create or update one file on GitHub through the contents API."""
    settings = settings or github_settings()
    if not settings:
        return "GitHub saving is not set up (see DEPLOY.md, 'Sign in and save online')."
    relative = Path(path).resolve().relative_to(BASE_DIR).as_posix()
    url = f"{API}/repos/{settings['repo'].strip()}/contents/{relative}"
    headers = {"Authorization": f"Bearer {settings['token'].strip()}", "Accept": "application/vnd.github+json"}
    current = session.get(url, headers=headers, params={"ref": settings["branch"]}, timeout=20)
    body = {"message": message, "branch": settings["branch"],
            "content": base64.b64encode(Path(path).read_bytes()).decode()}
    if current.status_code == 200:
        body["sha"] = current.json()["sha"]
    response = session.put(url, headers=headers, json=body, timeout=30)
    if response.status_code not in (200, 201):
        detail = check_github(settings, session) if response.status_code in (401, 403, 404) else ""
        return f"Not saved to GitHub ({response.status_code}). {detail}".strip()
    return ""


def persist(path: Path, message: str) -> None:
    """Call after writing a file. Online → commit it to GitHub if this person may save it.

    The owner may save anything; a signed-in user only their own work record.
    """
    if not cloud_mode():
        return
    own_files = [progress_path()]
    user = current_user()
    if user and user != "owner":
        import my_portfolio
        own_files.append(my_portfolio.portfolio_file(user))
    own = any(f is not None and Path(path).resolve() == f.resolve() for f in own_files)
    if not (is_owner() or own):
        return
    try:
        problem = commit_file(Path(path), message)
    except Exception as error:
        problem = f"Not saved to GitHub ({type(error).__name__})."
    # Kept in the session so the result is still visible after the page reruns
    st.session_state["vt_save_status"] = problem or f"Saved to GitHub: {Path(path).name}"
    if problem:
        st.warning(problem)
    else:
        st.toast("Saved to GitHub")


def owner_only_note(action: str = "save") -> None:
    st.caption(f"Only the owner can {action}. You can try everything here without saving.")
