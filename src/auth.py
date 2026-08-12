"""
auth.py — Autenticação de usuários (e-mail + senha) com dois backends.

Armazenamento
-------------
- **Supabase (Postgres)** quando as credenciais estão em
  ``st.secrets["supabase"]`` — usado em produção (não perde cadastros).
- **Arquivo local** ``data/users.json`` como fallback para desenvolvimento.

As senhas NUNCA são guardadas em texto puro: PBKDF2-HMAC-SHA256 com sal
aleatório por usuário (biblioteca padrão).

Tabela esperada no Supabase (SQL fornecido na configuração):
    users(email text primary key, name text, salt text, hash text,
          plan text default 'free')
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as _secrets
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_USERS_FILE = _DATA_DIR / "users.json"
_ITERATIONS = 200_000

_TABLE = "users"
_client_cache = {}


# --------------------------------------------------------------------------- #
# Seleção de backend
# --------------------------------------------------------------------------- #
def _supabase_creds() -> tuple[str, str] | None:
    """Lê URL e chave do Supabase de st.secrets (ou variáveis de ambiente)."""
    url = key = None
    try:
        import streamlit as st

        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except Exception:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    if url and key and "COLE_AQUI" not in str(url) and "COLE_AQUI" not in str(key):
        return str(url).strip(), str(key).strip()
    return None


def using_supabase() -> bool:
    return _supabase_creds() is not None


def _client():
    creds = _supabase_creds()
    if not creds:
        return None
    url, key = creds
    if url not in _client_cache:
        from supabase import create_client

        _client_cache[url] = create_client(url, key)
    return _client_cache[url]


# --------------------------------------------------------------------------- #
# Backend: arquivo local (fallback)
# --------------------------------------------------------------------------- #
def _json_load() -> dict:
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _json_save(users: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _USERS_FILE)


# --------------------------------------------------------------------------- #
# Operações de baixo nível (abstraem o backend)
# --------------------------------------------------------------------------- #
def _fetch(email: str) -> dict | None:
    """Retorna o registro bruto do usuário (com salt/hash) ou None."""
    if using_supabase():
        res = _client().table(_TABLE).select("*").eq("email", email).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    return _json_load().get(email)


def _insert(email: str, record: dict) -> None:
    if using_supabase():
        _client().table(_TABLE).insert({"email": email, **record}).execute()
    else:
        users = _json_load()
        users[email] = record
        _json_save(users)


def _update(email: str, fields: dict) -> None:
    if using_supabase():
        _client().table(_TABLE).update(fields).eq("email", email).execute()
    else:
        users = _json_load()
        if email in users:
            users[email].update(fields)
            _json_save(users)


# --------------------------------------------------------------------------- #
# Hash de senha
# --------------------------------------------------------------------------- #
def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return dk.hex()


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    candidate = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, hash_hex)


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register(email: str, password: str, name: str = "") -> tuple[bool, str]:
    email = _normalize_email(email)
    if "@" not in email or "." not in email:
        return False, "E-mail inválido."
    if len(password) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."

    if _fetch(email):
        return False, "Já existe uma conta com este e-mail."

    salt = _secrets.token_bytes(16)
    record = {
        "name": name.strip() or email.split("@")[0],
        "salt": salt.hex(),
        "hash": _hash_password(password, salt),
        "plan": "free",
    }
    try:
        _insert(email, record)
    except Exception as exc:
        return False, f"Erro ao criar conta: {exc}"
    return True, "Conta criada com sucesso!"


def authenticate(email: str, password: str) -> tuple[bool, str]:
    email = _normalize_email(email)
    user = _fetch(email)
    if not user or not _verify_password(password, user["salt"], user["hash"]):
        return False, "E-mail ou senha incorretos."
    return True, "Login efetuado."


def get_user(email: str) -> dict | None:
    email = _normalize_email(email)
    user = _fetch(email)
    if not user:
        return None
    return {"email": email, "name": user["name"], "plan": user.get("plan", "free")}


def set_plan(email: str, plan_key: str) -> bool:
    email = _normalize_email(email)
    if not _fetch(email):
        return False
    _update(email, {"plan": plan_key})
    return True
