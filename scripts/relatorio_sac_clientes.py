#!/usr/bin/env python3
"""Calcula indicadores de SAC e comportamento por cliente."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean


GRUPOS = (False, True)


def numero(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.2f}"


def numero_percentual(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.2f}%"


def percentual(parte: int, total: int) -> str:
    return f"{100 * parte / total:.2f}%" if total else "0.00%"


def calcular(banco: Path) -> tuple[dict[bool, Counter[str]], dict[bool, dict[str, float | int | None]]]:
    with sqlite3.connect(banco) as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(clientes)")}
        if "inativo" not in colunas:
            raise RuntimeError("Execute primeiro scripts/marcar_clientes_inativos.py.")

        clientes = dict(conexao.execute("SELECT id_cliente, inativo FROM clientes"))
        ids_por_grupo = {
            grupo: {id_cliente for id_cliente, inativo in clientes.items() if bool(inativo) == grupo}
            for grupo in GRUPOS
        }
        sac_por_cliente: Counter[str] = Counter()
        ultimo_sac: dict[str, date] = {}
        motivos = {False: Counter(), True: Counter()}
        for id_cliente, ano_mes, tickets, motivo in conexao.execute(
            "SELECT id_cliente, ano_mes, tickets_sac, motivo_sac_principal FROM interacoes"
        ):
            tickets = tickets or 0
            if id_cliente not in clientes or tickets <= 0:
                continue
            grupo = bool(clientes[id_cliente])
            sac_por_cliente[id_cliente] += tickets
            motivos[grupo][motivo or "SEM MOTIVO INFORMADO"] += tickets
            data_sac = date.fromisoformat(f"{ano_mes}-01")
            ultimo_sac[id_cliente] = max(ultimo_sac.get(id_cliente, data_sac), data_sac)

        pedidos_por_cliente: defaultdict[str, list[tuple[date, bool, float | None]]] = defaultdict(list)
        for id_cliente, data_pedido, cupom, atraso in conexao.execute(
            "SELECT id_cliente, data_pedido, cupom_utilizado, atraso_entrega_dias FROM pedidos"
        ):
            if id_cliente in clientes and data_pedido:
                pedidos_por_cliente[id_cliente].append(
                    (date.fromisoformat(data_pedido), bool(cupom), atraso)
                )

    indicadores = {}
    for grupo in GRUPOS:
        ids = ids_por_grupo[grupo]
        sac_por_cliente_grupo = [sac_por_cliente[id_cliente] for id_cliente in ids]
        taxas_cupom = []
        atrasos_maximos = []
        atrasos_ultimos = []
        intervalos_sac_compra = []
        for id_cliente in ids:
            pedidos = sorted(pedidos_por_cliente[id_cliente])
            if pedidos:
                taxas_cupom.append(sum(pedido[1] for pedido in pedidos) / len(pedidos) * 100)
                atrasos = [float(pedido[2]) for pedido in pedidos if pedido[2] is not None]
                if atrasos:
                    atrasos_maximos.append(max(atrasos))
                if pedidos[-1][2] is not None:
                    atrasos_ultimos.append(float(pedidos[-1][2]))
                if id_cliente in ultimo_sac:
                    intervalos_sac_compra.append(abs((pedidos[-1][0] - ultimo_sac[id_cliente]).days))

        indicadores[grupo] = {
            "sac_cliente": mean(sac_por_cliente_grupo) if sac_por_cliente_grupo else 0,
            "cupom_cliente": mean(taxas_cupom) if taxas_cupom else 0,
            "atraso_maximo": mean(atrasos_maximos) if atrasos_maximos else None,
            "atraso_ultimo": mean(atrasos_ultimos) if atrasos_ultimos else None,
            "dias_sac_compra": mean(intervalos_sac_compra) if intervalos_sac_compra else None,
            "_sac_clientes": sac_por_cliente_grupo,
            "_taxas_cupom": taxas_cupom,
            "_atrasos_maximos": atrasos_maximos,
            "_atrasos_ultimos": atrasos_ultimos,
            "_intervalos_sac_compra": intervalos_sac_compra,
        }

    indicadores[None] = {}
    for chave in ("_sac_clientes", "_taxas_cupom"):
        valores = [valor for grupo in GRUPOS for valor in indicadores[grupo][chave]]
        chave_publica = "sac_cliente" if chave == "_sac_clientes" else "cupom_cliente"
        indicadores[None][chave_publica] = mean(valores) if valores else 0
    for chave in ("_atrasos_maximos", "_atrasos_ultimos", "_intervalos_sac_compra"):
        valores = [valor for grupo in GRUPOS for valor in indicadores[grupo][chave]]
        chave_publica = {
            "_atrasos_maximos": "atraso_maximo",
            "_atrasos_ultimos": "atraso_ultimo",
            "_intervalos_sac_compra": "dias_sac_compra",
        }[chave]
        indicadores[None][chave_publica] = mean(valores) if valores else None
    motivos[None] = motivos[False] + motivos[True]
    return motivos, indicadores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        motivos, indicadores = calcular(args.banco)
    except (sqlite3.Error, RuntimeError, ValueError) as erro:
        raise SystemExit(f"Não foi possível gerar o relatório: {erro}") from erro

    print("## 1. Distribuição dos motivos de SAC")
    print("| Motivo | Ativos | Inativos | Total |")
    print("| --- | ---: | ---: | ---: |")
    total_sacs = sum(motivos[None].values())
    for motivo in sorted(motivos[None]):
        ativos = motivos[False][motivo]
        inativos = motivos[True][motivo]
        total = motivos[None][motivo]
        print(
            f"| {motivo} | {ativos} ({percentual(ativos, sum(motivos[False].values()))}) "
            f"| {inativos} ({percentual(inativos, sum(motivos[True].values()))}) "
            f"| {total} ({percentual(total, total_sacs)}) |"
        )

    print("\n## 2–6. Indicadores por cliente")
    print("| Indicador | Ativos | Inativos | Total |")
    print("| --- | ---: | ---: | ---: |")
    linhas = [
        ("quantidade média de SACs por cliente", "sac_cliente"),
        ("percentual médio de pedidos com cupom por cliente", "cupom_cliente"),
        ("atraso máximo médio por cliente", "atraso_maximo"),
        ("atraso médio do último pedido", "atraso_ultimo"),
        ("dias médios entre o último SAC e a última compra", "dias_sac_compra"),
    ]
    for nome, chave in linhas:
        formatar = numero_percentual if chave == "cupom_cliente" else numero
        print(
            f"| {nome} | {formatar(indicadores[False][chave])} | "
            f"{formatar(indicadores[True][chave])} | {formatar(indicadores[None][chave])} |"
        )


if __name__ == "__main__":
    main()
