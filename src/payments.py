"""
payments.py — Integração com o Mercado Pago (Checkout Pro).

Fluxo
-----
1. O usuário logado clica em "Obter Premium".
2. Criamos uma *preferência* de pagamento (create_preference) com o valor do
   plano e o e-mail do usuário em `external_reference`.
3. Redirecionamos o usuário ao checkout do Mercado Pago (Pix, cartão, boleto).
4. Ao pagar, o Mercado Pago devolve o usuário para a URL do app com os
   parâmetros `payment_id`, `status` e `external_reference`.
5. Confirmamos o pagamento consultando a API (verify_payment) e, se aprovado,
   liberamos o plano Premium.

Credenciais
-----------
O Access Token é lido de `st.secrets["mercadopago"]["access_token"]`
(arquivo `.streamlit/secrets.toml`). NUNCA fica no código.
"""

from __future__ import annotations

import streamlit as st

try:
    import mercadopago
except ImportError:  # SDK ausente
    mercadopago = None


def _get_token() -> str | None:
    """Lê o Access Token dos secrets do Streamlit. Retorna None se não houver."""
    try:
        token = st.secrets["mercadopago"]["access_token"]
        token = str(token).strip()
        return token or None
    except Exception:
        return None


def is_configured() -> bool:
    """True se o SDK está instalado e o token está presente."""
    return mercadopago is not None and _get_token() is not None


def _sdk():
    return mercadopago.SDK(_get_token())


def create_preference(
    *,
    user_email: str,
    plan_name: str,
    price: float,
    base_url: str,
) -> tuple[bool, str]:
    """
    Cria a preferência de pagamento e retorna (sucesso, url_do_checkout | erro).

    `base_url` é o endereço público do app (ex.: https://cleandoc.streamlit.app),
    usado para o Mercado Pago devolver o usuário após o pagamento.
    """
    if not is_configured():
        return False, "Pagamento não configurado (Access Token ausente)."

    sdk = _sdk()
    preference_data = {
        "items": [
            {
                "title": f"CleanDoc — Plano {plan_name}",
                "description": "Acesso vitalício ao plano Premium do CleanDoc.",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price),
            }
        ],
        "payer": {"email": user_email},
        "external_reference": user_email,
        "back_urls": {
            "success": base_url,
            "failure": base_url,
            "pending": base_url,
        },
        "auto_return": "approved",
        "statement_descriptor": "CLEANDOC",
    }
    try:
        result = sdk.preference().create(preference_data)
        resp = result.get("response", {})
        # init_point = produção; sandbox_init_point = ambiente de teste
        url = resp.get("init_point") or resp.get("sandbox_init_point")
        if url:
            return True, url
        return False, f"Resposta inesperada do Mercado Pago: {resp}"
    except Exception as exc:
        return False, f"Erro ao criar pagamento: {exc}"


def verify_payment(payment_id: str) -> tuple[bool, str, str | None]:
    """
    Consulta um pagamento e retorna (aprovado, status, email_do_pagador).

    Usado no retorno do checkout para confirmar antes de liberar o Premium.
    """
    if not is_configured():
        return False, "unconfigured", None
    try:
        sdk = _sdk()
        result = sdk.payment().get(payment_id)
        resp = result.get("response", {})
        status = resp.get("status", "unknown")
        email = resp.get("external_reference")
        return (status == "approved"), status, email
    except Exception as exc:
        return False, f"erro: {exc}", None
