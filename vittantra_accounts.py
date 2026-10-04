"""
User accounts for the online app: anyone can create a username and password
and keep their own Academy progress.

Passwords are never stored. Each account keeps a random salt and a PBKDF2-SHA256
fingerprint (the standard way to store passwords); the fingerprint cannot be
turned back into the password. Accounts live in `users.json`, which is committed
to the (public) repository, so usernames are public and people should not reuse
a password they use elsewhere.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import date
from pathlib import Path
from typing import Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"
PROGRESS_DIR = BASE_DIR / "academy_progress"
ITERATIONS = 310_000                 # OWASP 2023 guidance for PBKDF2-SHA256
MIN_PASSWORD = 8
RESERVED = {"owner", "admin", "administrator", "vittantra", "root", "system"}
USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{2,19}$")


def hash_password(password: str, salt: Optional[str] = None, iterations: int = ITERATIONS) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return salt, digest.hex()


def verify_password(password: str, record: dict) -> bool:
    if not record or "salt" not in record or "hash" not in record:
        return False
    _, digest = hash_password(password, record["salt"], int(record.get("iterations", ITERATIONS)))
    return hmac.compare_digest(digest, record["hash"])


def normalize(username: str) -> str:
    return username.strip().lower()


def username_problem(username: str) -> str:
    """Empty string when the username is allowed, otherwise the reason."""
    name = normalize(username)
    if not USERNAME.match(name):
        return "Use 3–20 characters: letters, numbers, - or _, starting with a letter or number."
    if name in RESERVED:
        return "That username is reserved. Please choose another."
    return ""


def password_problem(password: str) -> str:
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if password.strip() != password:
        return "The password cannot start or end with a space."
    return ""


def load_users(path: Path = USERS_FILE) -> dict:
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_users(users: dict, path: Path = USERS_FILE) -> None:
    Path(path).write_text(json.dumps(users, indent=2, sort_keys=True))


def add_user(users: dict, username: str, password: str) -> Tuple[dict, str]:
    """Return (updated users, problem). The input dict is not modified."""
    problem = username_problem(username) or password_problem(password)
    name = normalize(username)
    if not problem and name in users:
        problem = "That username is taken. Please choose another."
    if problem:
        return users, problem
    salt, digest = hash_password(password)
    updated = dict(users)
    updated[name] = {"salt": salt, "hash": digest, "iterations": ITERATIONS, "created": date.today().isoformat()}
    return updated, ""


def check_login(users: dict, username: str, password: str) -> Optional[str]:
    """The normalized username when the password matches, else None."""
    name = normalize(username)
    return name if verify_password(password, users.get(name, {})) else None


def progress_file(username: str) -> Path:
    return PROGRESS_DIR / f"{normalize(username)}.json"
