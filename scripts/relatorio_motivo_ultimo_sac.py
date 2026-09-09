#!/usr/bin/env python3
"""Distribui o motivo do último SAC ocorrido após a última compra."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path


GRUPOS = (False, True, None)
ORDEM_MOTIVOS = (
    "ATRASO NA ENTREGA",
    "CANCELAMENTO",
    "PRODUTO AVARIADO",
    "PROBLEMA NO PAGAMENTO",
    "TROCA OU DEVOLUCAO",
    "DUVIDA SOBRE PRODUTO",
    "SEM MOTIVO INFORMADO",
)
NOMES_MOTIVOS = {
    "ATRASO NA ENTREGA": "Atraso na entrega",
    "CANCELAMENTO": "Cancelamento",
    "PRODUTO AVARIADO": "Produto avariado",
    "PROBLEMA NO PAGAMENTO": "Problema no pagamento",
    "TROCA OU DEVOLUCAO": "Troca ou devolução",
    "DUVIDA SOBRE PRODUTO": "Dúvida sobre produto",
    "SEM MOTIVO INFORMADO": "Sem motivo informado",
}


def percentual(parte: int, total: int) -> str:
    return f"{100 * parte / total:.2f}%" if total else "0.00%"


def calcular(banco: Path) -> tuple[dict[bool | None, Counter[str]], dict[bool | None, int]]:
    with sqlite3.connect(banco) as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(clientes)")}
        if "inativo" not in colunas:
            raise RuntimeError("Execute primeiro scripts/marcar_clientes_inativos.py.")

        clientes = dict(conexao.execute("SELECT id_cliente, inativo FROM clientes"))
        ultima_compra = dict(conexao.execute(
            "SELECT id_cliente, MAX(data_pedido) FROM pedidos WHERE data_pedido IS NOT NULL GROUP BY id_cliente"
        ))
        ultimo_sac: dict[str, tuple[date, int, str]] = {}
        for id_interacao, id_cliente, ano_mes, motivo in conexao.execute(
            "SELECT id, id_cliente, ano_mes, motivo_sac_principal FROM interacoes WHERE tickets_sac > 0"
        ):
            if id_cliente not in clientes:
                continue
            registro = (date.fromisoformat(f"{ano_mes}-01"), id_interacao, motivo or "SEM MOTIVO INFORMADO")
            if id_cliente not in ultimo_sac or registro[:2] > ultimo_sac[id_cliente][:2]:
                ultimo_sac[id_cliente] = registro

    contagens = {grupo: Counter() for grupo in GRUPOS}
    bases = {grupo: 0 for grupo in GRUPOS}
    for id_cliente, (data_sac, _, motivo) in ultimo_sac.items():
        compra = ultima_compra.get(id_cliente)
        if compra is None or data_sac <= date.fromisoformat(compra):
            continue
        grupo = bool(clientes[id_cliente])
        contagens[grupo][motivo] += 1
        bases[grupo] += 1

    for motivo in ORDEM_MOTIVOS:
        contagens[None][motivo] = contagens[False][motivo] + contagens[True][motivo]
    bases[None] = bases[False] + bases[True]
    return contagens, bases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        contagens, bases = calcular(args.banco)
    except (sqlite3.Error, RuntimeError, ValueError) as erro:
        raise SystemExit(f"Não foi possível gerar o relatório: {erro}") from erro

    print("| Motivo do último SAC após última compra | Ativos | Inativos | Total |")
    print("| --- | ---: | ---: | ---: |")
    for motivo in ORDEM_MOTIVOS:
        valores = [
            f"{contagens[grupo][motivo]} ({percentual(contagens[grupo][motivo], bases[grupo])})"
            for grupo in GRUPOS
        ]
        print(f"| {NOMES_MOTIVOS[motivo]} | {valores[0]} | {valores[1]} | {valores[2]} |")
    print("\nBase: clientes cujo último SAC ocorreu após a última compra.")


if __name__ == "__main__":
    main()
