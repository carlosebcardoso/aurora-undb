#!/usr/bin/env python3
"""Cria a tabela analise_clientes com métricas de comportamento de pedidos."""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median, pstdev


def criar_tabela(banco: Path) -> int:
    """Recria a tabela analise_clientes e retorna a quantidade de clientes."""
    with sqlite3.connect(banco) as conexao:
        colunas_clientes = {
            coluna[1]
            for coluna in conexao.execute("PRAGMA table_info(clientes)")
        }
        if "inativo" not in colunas_clientes:
            raise RuntimeError(
                "A coluna 'inativo' não existe em clientes. "
                "Execute primeiro scripts/marcar_clientes_inativos.py."
            )

        pedidos_por_cliente: dict[str, list[date]] = defaultdict(list)
        clientes = conexao.execute(
            """
            SELECT id_cliente, uf, faixa_etaria, canal_aquisicao, tier_clube, inativo
            FROM clientes
            ORDER BY id_cliente
            """
        ).fetchall()
        pedidos = conexao.execute(
            """
            SELECT id_cliente, data_pedido
            FROM pedidos
            WHERE data_pedido IS NOT NULL
            ORDER BY id_cliente, data_pedido
            """
        )
        for id_cliente, data_pedido in pedidos:
            pedidos_por_cliente[id_cliente].append(date.fromisoformat(data_pedido))

        registros = []
        for id_cliente, uf, faixa_etaria, canal, tier_clube, inativo in clientes:
            datas = pedidos_por_cliente[id_cliente]
            intervalos = [
                (atual - anterior).days
                for anterior, atual in zip(datas, datas[1:])
            ]
            registros.append(
                (
                    id_cliente,
                    uf,
                    faixa_etaria,
                    canal,
                    tier_clube,
                    bool(inativo),
                    datas[-1].isoformat() if datas else None,
                    round(mean(intervalos), 2) if intervalos else None,
                    round(pstdev(intervalos), 2) if len(intervalos) > 1 else None,
                    max(intervalos) if intervalos else None,
                    min(intervalos) if intervalos else None,
                    round(median(intervalos), 2) if intervalos else None,
                )
            )

        conexao.execute("DROP TABLE IF EXISTS analise_clientes")
        conexao.execute(
            """
            CREATE TABLE analise_clientes (
                id_cliente TEXT PRIMARY KEY,
                uf TEXT,
                faixa_etaria TEXT,
                canal TEXT,
                tier_clube TEXT,
                inativo BOOLEAN NOT NULL,
                data_ultimo_pedido DATE,
                media_entre_pedidos REAL,
                desvio_pedidos REAL,
                maior_intervalo INTEGER,
                menor_intervalo INTEGER,
                mediana_pedidos REAL
            )
            """
        )
        conexao.executemany(
            """
            INSERT INTO analise_clientes (
                id_cliente, uf, faixa_etaria, canal, tier_clube, inativo,
                data_ultimo_pedido, media_entre_pedidos, desvio_pedidos,
                maior_intervalo, menor_intervalo, mediana_pedidos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            registros,
        )

    return len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco",
        type=Path,
        default=Path("dados.sqlite3"),
        help="arquivo SQLite que será atualizado (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()

    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")

    try:
        quantidade = criar_tabela(args.banco)
    except (sqlite3.Error, RuntimeError, ValueError) as erro:
        raise SystemExit(f"Não foi possível criar a análise: {erro}") from erro
    print(f"Tabela 'analise_clientes' criada com {quantidade} clientes.")


if __name__ == "__main__":
    main()
