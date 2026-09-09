#!/usr/bin/env python3
"""Calcula indicadores de clientes ativos e inativos."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median


def numero(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.2f}"


def percentual(parte: int, total: int) -> str:
    return f"{100 * parte / total:.2f}%" if total else "0.00%"


def categorias_mais_compradas(contagem: Counter[str]) -> str:
    if not contagem:
        return "—"
    return "; ".join(f"{nome} ({quantidade:g})" for nome, quantidade in contagem.most_common(3))


def calcular_indicadores(banco: Path) -> dict[bool, dict[str, object]]:
    with sqlite3.connect(banco) as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(clientes)")}
        if "inativo" not in colunas:
            raise RuntimeError("Execute primeiro scripts/marcar_clientes_inativos.py.")

        clientes = dict(conexao.execute("SELECT id_cliente, inativo FROM clientes"))
        ids_por_grupo = {
            grupo: {id_cliente for id_cliente, inativo in clientes.items() if bool(inativo) == grupo}
            for grupo in (False, True)
        }
        pedidos = {}
        datas_por_cliente: defaultdict[str, list[date]] = defaultdict(list)
        for id_pedido, id_cliente, data_pedido, cupom, atraso in conexao.execute(
            "SELECT id_pedido, id_cliente, data_pedido, cupom_utilizado, atraso_entrega_dias FROM pedidos"
        ):
            data = date.fromisoformat(data_pedido) if data_pedido else None
            pedidos[id_pedido] = (id_cliente, data, bool(cupom), atraso)
            if data:
                datas_por_cliente[id_cliente].append(data)

        valor_por_pedido: defaultdict[str, float] = defaultdict(float)
        categorias_por_grupo = {grupo: Counter() for grupo in (False, True)}
        for id_pedido, categoria, quantidade, valor_unitario, desconto in conexao.execute(
            "SELECT id_pedido, categoria, quantidade, valor_unitario, valor_desconto FROM pedido_itens"
        ):
            quantidade = quantidade or 0
            valor_por_pedido[id_pedido] += quantidade * (valor_unitario or 0) - (desconto or 0)
            pedido = pedidos.get(id_pedido)
            if pedido and categoria and pedido[0] in clientes:
                categorias_por_grupo[bool(clientes[pedido[0]])][categoria] += quantidade

        clientes_com_sac = {False: set(), True: set()}
        sac_total = Counter()
        sac_nao_resolvido = Counter()
        for id_cliente, tickets_sac, resolvido in conexao.execute(
            "SELECT id_cliente, tickets_sac, ticket_resolvido FROM interacoes"
        ):
            if id_cliente in clientes and (tickets_sac or 0) > 0:
                grupo = bool(clientes[id_cliente])
                clientes_com_sac[grupo].add(id_cliente)
                sac_total[grupo] += 1
                if resolvido == 0:
                    sac_nao_resolvido[grupo] += 1

        tiers_canais = {False: (Counter(), Counter()), True: (Counter(), Counter())}
        for grupo in (False, True):
            for tier, canal in conexao.execute(
                "SELECT tier_clube, canal_aquisicao FROM clientes WHERE inativo = ?", (int(grupo),)
            ):
                if tier:
                    tiers_canais[grupo][0][tier] += 1
                if canal:
                    tiers_canais[grupo][1][canal] += 1

    resultado = {}
    for grupo in (False, True):
        ids = ids_por_grupo[grupo]
        valores = [valor_por_pedido.get(id_pedido, 0) for id_pedido, pedido in pedidos.items() if pedido[0] in ids]
        pedidos_por_cliente = Counter(pedido[0] for pedido in pedidos.values() if pedido[0] in ids)
        total_pedidos = sum(pedidos_por_cliente.values())
        atrasos = [float(pedido[3]) for pedido in pedidos.values() if pedido[0] in ids and pedido[3] is not None]
        pedidos_com_atraso = sum(
            pedido[3] is not None and pedido[3] > 0
            for pedido in pedidos.values()
            if pedido[0] in ids
        )
        clientes_com_cupom = {pedido[0] for pedido in pedidos.values() if pedido[0] in ids and pedido[2]}
        intervalos = []
        for id_cliente in ids:
            datas = sorted(datas_por_cliente[id_cliente])
            intervalos.extend((atual - anterior).days for anterior, atual in zip(datas, datas[1:]))
        tier, canal = tiers_canais[grupo]
        resultado[grupo] = {
            "quantidade": len(ids),
            "ticket": mean(valores) if valores else None,
            "pedidos": mean([pedidos_por_cliente[id_cliente] for id_cliente in ids]) if ids else None,
            "intervalo_medio": mean(intervalos) if intervalos else None,
            "intervalo_mediano": median(intervalos) if intervalos else None,
            "atraso": mean(atrasos) if atrasos else None,
            "sac": percentual(len(clientes_com_sac[grupo]), len(ids)),
            "sac_nao_resolvido": percentual(sac_nao_resolvido[grupo], sac_total[grupo]),
            "cupom": percentual(len(clientes_com_cupom), len(ids)),
            "pedidos_com_atraso": percentual(pedidos_com_atraso, total_pedidos),
            "categorias": categorias_mais_compradas(categorias_por_grupo[grupo]),
            "tier": tier.most_common(1)[0][0] if tier else "—",
            "canal": canal.most_common(1)[0][0] if canal else "—",
            "_soma_ticket": sum(valores),
            "_total_pedidos": total_pedidos,
            "_intervalos": intervalos,
            "_atrasos": atrasos,
            "_clientes_sac": len(clientes_com_sac[grupo]),
            "_sac_total": sac_total[grupo],
            "_sac_nao_resolvido": sac_nao_resolvido[grupo],
            "_clientes_cupom": len(clientes_com_cupom),
            "_pedidos_com_atraso": pedidos_com_atraso,
        }

    todos = resultado[False], resultado[True]
    intervalos_totais = todos[0]["_intervalos"] + todos[1]["_intervalos"]
    atrasos_totais = todos[0]["_atrasos"] + todos[1]["_atrasos"]
    quantidade_total = sum(dados["quantidade"] for dados in todos)
    pedidos_total = sum(dados["_total_pedidos"] for dados in todos)
    sac_total_geral = sum(dados["_sac_total"] for dados in todos)
    resultado[None] = {
        "quantidade": quantidade_total,
        "ticket": sum(dados["_soma_ticket"] for dados in todos) / pedidos_total if pedidos_total else None,
        "pedidos": pedidos_total / quantidade_total if quantidade_total else None,
        "intervalo_medio": mean(intervalos_totais) if intervalos_totais else None,
        "intervalo_mediano": median(intervalos_totais) if intervalos_totais else None,
        "atraso": mean(atrasos_totais) if atrasos_totais else None,
        "sac": percentual(sum(dados["_clientes_sac"] for dados in todos), quantidade_total),
        "sac_nao_resolvido": percentual(sum(dados["_sac_nao_resolvido"] for dados in todos), sac_total_geral),
        "cupom": percentual(sum(dados["_clientes_cupom"] for dados in todos), quantidade_total),
        "pedidos_com_atraso": percentual(sum(dados["_pedidos_com_atraso"] for dados in todos), pedidos_total),
    }
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        dados = calcular_indicadores(args.banco)
    except (sqlite3.Error, RuntimeError, ValueError) as erro:
        raise SystemExit(f"Não foi possível gerar o relatório: {erro}") from erro

    print("| Indicador | Ativos | Inativos | Total |")
    print("| --- | ---: | ---: | ---: |")
    linhas = [
        ("quantidade de clientes", lambda d: str(d["quantidade"])),
        ("ticket médio", lambda d: numero(d["ticket"])),
        ("nº médio de pedidos", lambda d: numero(d["pedidos"])),
        ("intervalo médio entre pedidos", lambda d: numero(d["intervalo_medio"])),
        ("intervalo mediano entre pedidos", lambda d: numero(d["intervalo_mediano"])),
        ("atraso médio de entrega", lambda d: numero(d["atraso"])),
        ("percentual com SAC", lambda d: str(d["sac"])),
        ("percentual de SAC não resolvido", lambda d: str(d["sac_nao_resolvido"])),
        ("percentual que utilizou cupom", lambda d: str(d["cupom"])),
        ("percentual de pedidos com atraso", lambda d: str(d["pedidos_com_atraso"])),
    ]
    for nome, formatar in linhas:
        print(
            f"| {nome} | {formatar(dados[False])} | {formatar(dados[True])} "
            f"| {formatar(dados[None])} |"
        )


if __name__ == "__main__":
    main()
