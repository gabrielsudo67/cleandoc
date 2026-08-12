"""
plans.py — Definição dos planos (grátis e premium) e seus limites.

Centralizar aqui facilita ajustar preços e limites sem mexer no resto do código.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price: float                # em R$
    one_time: bool              # True = pagamento único; False = mensal/grátis
    max_file_mb: int            # tamanho máximo por arquivo
    batch: bool                 # remoção em lote liberada?
    max_files_batch: int        # nº máximo de arquivos por vez
    perks: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=lambda: ["PNG", "JPG"])  # saídas liberadas

    @property
    def price_label(self) -> str:
        """Texto amigável do preço, ex.: 'R$ 30,00 (pagamento único)'."""
        if self.price <= 0:
            return "R$ 0"
        valor = f"R$ {self.price:.2f}".replace(".", ",")
        return f"{valor} (pagamento único)" if self.one_time else f"{valor}/mês"


FREE = Plan(
    key="free",
    name="Grátis",
    price=0.0,
    one_time=False,
    max_file_mb=10,
    batch=False,
    max_files_batch=1,
    perks=[
        "1 arquivo por vez",
        "Até 10 MB por arquivo",
        "Limpeza HSV + limiarização adaptativa",
        "Download em PNG ou JPG",
    ],
    formats=["PNG", "JPG"],
)

PREMIUM = Plan(
    key="premium",
    name="Premium",
    price=30.00,
    one_time=True,
    max_file_mb=100,
    batch=True,
    max_files_batch=50,
    perks=[
        "Pagamento único — acesso vitalício",
        "Exportar em PDF e Word (DOCX)",
        "Remoção em lote (até 50 arquivos)",
        "Até 100 MB por arquivo",
        "Download de todos em .zip",
        "Prioridade de processamento",
        "Suporte por e-mail",
    ],
    formats=["PDF", "Word (DOCX)", "PNG", "JPG"],
)

PLANS = {FREE.key: FREE, PREMIUM.key: PREMIUM}


def get_plan(key: str) -> Plan:
    return PLANS.get(key, FREE)
