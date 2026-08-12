"""
stats.py — Métricas para o Painel do Dono (área de administrador).

Lê os cadastros do mesmo backend do auth (Supabase em produção, JSON local
em desenvolvimento). O contador de visitas é opcional: se a tabela `visits`
não existir, as funções simplesmente ignoram (o painel funciona mesmo assim).
"""

from __future__ import annotations

from datetime import datetime

from src import auth


def get_all_users() -> list[dict]:
    """Retorna todos os usuários (sem dados sensíveis: só email, nome, plano, data)."""
    if auth.using_supabase():
        try:
            res = (
                auth._client()
                .table("users")
                .select("email,name,plan,created_at")
                .execute()
            )
            return res.data or []
        except Exception:
            return []
    # fallback local
    data = auth._json_load()
    return [{"email": e, **v} for e, v in data.items()]


def summarize(users: list[dict], premium_price: float) -> dict:
    total = len(users)
    premium = sum(1 for u in users if u.get("plan") == "premium")
    return {
        "total": total,
        "premium": premium,
        "free": total - premium,
        "revenue": premium * premium_price,
        "conversion": (premium / total * 100) if total else 0.0,
    }


def signups_by_day(users: list[dict]) -> dict[str, int]:
    """Agrupa cadastros por dia (usa created_at quando disponível)."""
    counts: dict[str, int] = {}
    for u in users:
        raw = u.get("created_at")
        if not raw:
            continue
        try:
            # created_at do Supabase vem como ISO (ex.: 2026-08-12T13:00:00+00:00)
            day = str(raw)[:10]
            datetime.strptime(day, "%Y-%m-%d")  # valida
            counts[day] = counts.get(day, 0) + 1
        except (ValueError, TypeError):
            continue
    return dict(sorted(counts.items()))


# --------------------------------------------------------------------------- #
# Contador de visitas (opcional — requer a tabela `visits` no Supabase)
# --------------------------------------------------------------------------- #
def record_visit() -> None:
    """Registra 1 visita. Silencioso se a tabela não existir."""
    if not auth.using_supabase():
        return
    try:
        auth._client().table("visits").insert({}).execute()
    except Exception:
        pass


def get_visit_count() -> int | None:
    """Total de visitas, ou None se a tabela `visits` não existir."""
    if not auth.using_supabase():
        return None
    try:
        res = auth._client().table("visits").select("*", count="exact").execute()
        return res.count
    except Exception:
        return None
