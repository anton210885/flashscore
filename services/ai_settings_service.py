"""Lokale KI-/API-Einstellungen (.env) — Keys nie im Klartext an die UI zurückgeben."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT, ".env")
ENV_EXAMPLE_PATH = os.path.join(ROOT, ".env.example")

_OPENAI_KEY_RE = re.compile(r"^OPENAI_API_KEY\s*=\s*(.*)\s*$", re.MULTILINE)
_OPENAI_MODEL_RE = re.compile(r"^OPENAI_MODEL\s*=\s*(.*)\s*$", re.MULTILINE)

DEFAULT_MODEL = "gpt-4o-mini"


def _strip_quotes(v: str) -> str:
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def _read_env_file(path: str = ENV_PATH) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_env_file(content: str, path: str = ENV_PATH) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content if content.endswith("\n") or content == "" else content + "\n")


def _upsert_env_var(content: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pat.search(content):
        return pat.sub(line, content, count=1)
    body = content.rstrip("\n")
    if body:
        return body + "\n" + line + "\n"
    return line + "\n"


def _remove_env_var(content: str, key: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}\s*=.*\n?", re.MULTILINE)
    return pat.sub("", content)


def get_openai_api_key() -> Optional[str]:
    """Key aus Prozess-Env oder .env-Datei."""
    env_key = _strip_quotes(os.environ.get("OPENAI_API_KEY") or "")
    if env_key:
        return env_key
    text = _read_env_file()
    m = _OPENAI_KEY_RE.search(text)
    if not m:
        return None
    key = _strip_quotes(m.group(1))
    return key or None


def get_openai_model() -> str:
    env_model = _strip_quotes(os.environ.get("OPENAI_MODEL") or "")
    if env_model:
        return env_model
    text = _read_env_file()
    m = _OPENAI_MODEL_RE.search(text)
    if m:
        val = _strip_quotes(m.group(1))
        if val:
            return val
    return DEFAULT_MODEL


def mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    k = key.strip()
    if len(k) <= 10:
        return "••••••••"
    return f"{k[:7]}…{k[-4:]}"


def settings_status() -> Dict[str, Any]:
    key = get_openai_api_key()
    return {
        "ok": True,
        "openai_configured": bool(key),
        "openai_key_masked": mask_key(key),
        "openai_model": get_openai_model(),
        "env_path": ".env",
        "env_exists": os.path.isfile(ENV_PATH),
    }


def save_openai_settings(*, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """Schreibt OPENAI_* in .env und aktualisiert os.environ für den laufenden Prozess."""
    text = _read_env_file()
    if not text.strip() and os.path.isfile(ENV_EXAMPLE_PATH):
        text = _read_env_file(ENV_EXAMPLE_PATH)

    if api_key is not None:
        key = _strip_quotes(str(api_key))
        if not key:
            raise ValueError("API-Key ist leer.")
        if not key.startswith("sk-"):
            raise ValueError("OpenAI-Key sieht ungültig aus (sollte mit sk- beginnen).")
        text = _upsert_env_var(text, "OPENAI_API_KEY", key)
        os.environ["OPENAI_API_KEY"] = key

    if model is not None:
        mod = _strip_quotes(str(model)) or DEFAULT_MODEL
        text = _upsert_env_var(text, "OPENAI_MODEL", mod)
        os.environ["OPENAI_MODEL"] = mod

    if "OPENAI_MODEL" not in text:
        text = _upsert_env_var(text, "OPENAI_MODEL", get_openai_model())

    _write_env_file(text)
    return settings_status()


def clear_openai_api_key() -> Dict[str, Any]:
    text = _remove_env_var(_read_env_file(), "OPENAI_API_KEY")
    _write_env_file(text)
    os.environ.pop("OPENAI_API_KEY", None)
    return settings_status()


def env_export_template(*, include_placeholder_key: bool = True) -> str:
    """Vorlage zum Download — User fügt nur den Key ein."""
    lines = [
        "# Flashscore Analytics — lokale Secrets (nicht committen)",
        "# 1) Datei als .env im Projektroot speichern",
        "# 2) OPENAI_API_KEY= durch deinen Key ersetzen (platform.openai.com → API keys)",
        "",
        f"OPENAI_API_KEY={'sk-...' if include_placeholder_key else ''}",
        f"OPENAI_MODEL={get_openai_model()}",
        "",
        "# sstats.net API-Key (für Loader/Live-Pipeline)",
        "SSTATS_API_KEY=",
        "",
    ]
    return "\n".join(lines)
