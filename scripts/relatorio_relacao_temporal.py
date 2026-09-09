#!/usr/bin/env python3
"""Calcula a relação temporal entre o último SAC e a última compra."""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path


GRUPOS = (False, True)


def percentual(parte: int, total: int) -> str:
    return f"{100 * parte / total:.2f}%" if total else "0.00%"


def calcular(banco: Path) -> tuple[dict[bool, dict[str, int]], dict[bool, int]]:
    with sqlite3.connect(banco) as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(clientes)")}
        if "inativo" not in colunas:
            raise RuntimeError("Execute primeiro scripts/marcar_clientes_inativos.py.")

        clientes = dict(conexao.execute("SELECT id_cliente, inativo FROM clientes"))
        ultima_compra: dict[str, date] = {}
        for id_cliente, data_pedido in conexao.execute(
            "SELECT id_cliente, MAX(data_pedido) FROM pedidos WHERE data_pedido IS NOT NULL GROUP BY id_cliente"
        ):
            ultima_compra[id_cliente] = date.fromisoformat(data_pedido)

        ultimo_sac: dict[str, date] = {}
        for id_cliente, ano_mes, tickets_sac in conexao.execute(
            "SELECT id_cliente, ano_mes, tickets_sac FROM interacoes"
        ):
            if id_cliente not in clientes or (tickets_sac or 0) <= 0:
                continue
            data_sac = date.fromisoformat(f"{ano_mes}-01")
            if id_cliente not in ultimo_sac or data_sac > ultimo_sac[id_cliente]:
                ultimo_sac[id_cliente] = data_sac

    contagens = defaultdict(lambda: defaultdict(int))
    bases = defaultdict(int)
    for id_cliente, grupo in clientes.items():
        if id_cliente not in ultima_compra or id_cliente not in ultimo_sac:
            continue
        grupo = bool(grupo)
        diferenca = (ultima_compra[id_cliente] - ultimo_sac[id_cliente]).days
        bases[grupo] += 1
        if diferenca > 0:
            contagens[grupo]["antes"] += 1
            if diferenca <= 30:
                contagens[grupo]["antes_30"] += 1
            if diferenca <= 90:
                contagens[grupo]["antes_90"] += 1
        elif diferenca < 0:
            contagens[grupo]["depois"] += 1

    contagens[None] = defaultdict(int)
    bases[None] = sum(bases[grupo] for grupo in GRUPOS)
    for grupo in GRUPOS:
        for chave, quantidade in contagens[grupo].items():
            contagens[None][chave] += quantidade
    return (
        {grupo: dict(contagens[grupo]) for grupo in (False, True, None)},
        {grupo: bases[grupo] for grupo in (False, True, None)},
    )


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

    print("| Relação temporal | Ativos | Inativos | Total |")
    print("| --- | ---: | ---: | ---: |")
    linhas = [
        ("Último SAC antes da última compra", "antes"),
        ("Último SAC depois da última compra", "depois"),
        ("SAC até 30 dias antes da última compra", "antes_30"),
        ("SAC até 90 dias antes da última compra", "antes_90"),
    ]
    for nome, chave in linhas:
        valores = [percentual(contagens[grupo][chave], bases[grupo]) for grupo in (False, True, None)]
        print(f"| {nome} | {valores[0]} | {valores[1]} | {valores[2]} |")
    print("\nBase: clientes com último SAC e última compra identificados.")


if __name__ == "__main__":
    main()
