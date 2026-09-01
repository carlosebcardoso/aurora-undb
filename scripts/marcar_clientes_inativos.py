#!/usr/bin/env python3
"""Adiciona e atualiza a marcação de clientes inativos."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text


DATA_CORTE = "2026-06-30"
LIMITE_DIAS = 180
TOLERANCIA_DIAS = 15


def garantir_coluna_inativo(banco: Path) -> None:
    """Cria a coluna somente se ela ainda não existir."""
    engine = create_engine(f"sqlite:///{banco}")
    with engine.begin() as conexao:
        colunas = {
            coluna[1]
            for coluna in conexao.execute(text("PRAGMA table_info(clientes)"))
        }
        if "inativo" not in colunas:
            conexao.execute(
                text("ALTER TABLE clientes ADD COLUMN inativo BOOLEAN NOT NULL DEFAULT 0")
            )

        conexao.execute(
            text(
                """
                WITH pedidos_com_anterior AS (
                    SELECT
                        id_cliente,
                        data_pedido,
                        LAG(data_pedido) OVER (
                            PARTITION BY id_cliente
                            ORDER BY data_pedido
                        ) AS pedido_anterior
                    FROM pedidos
                    WHERE data_pedido IS NOT NULL
                      AND data_pedido <= :data_corte
                ),
                intervalos AS (
                    SELECT
                        id_cliente,
                        data_pedido,
                        julianday(data_pedido) - julianday(pedido_anterior)
                            AS intervalo_dias
                    FROM pedidos_com_anterior
                    WHERE pedido_anterior IS NOT NULL
                ),
                intervalos_ordenados AS (
                    SELECT
                        id_cliente,
                        intervalo_dias,
                        ROW_NUMBER() OVER (
                            PARTITION BY id_cliente
                            ORDER BY intervalo_dias
                        ) AS posicao,
                        COUNT(*) OVER (PARTITION BY id_cliente) AS quantidade
                    FROM intervalos
                ),
                metricas AS (
                    SELECT
                        id_cliente,
                        AVG(intervalo_dias) AS media_entre_pedidos,
                        AVG(
                            CASE
                                WHEN posicao IN (
                                    (quantidade + 1) / 2,
                                    (quantidade + 2) / 2
                                ) THEN intervalo_dias
                            END
                        ) AS mediana_pedidos
                    FROM intervalos_ordenados
                    GROUP BY id_cliente
                ),
                ultimos AS (
                    SELECT id_cliente, MAX(data_pedido) AS data_ultimo_pedido
                    FROM pedidos
                    WHERE data_pedido IS NOT NULL
                      AND data_pedido <= :data_corte
                    GROUP BY id_cliente
                ),
                alvos AS (
                    SELECT
                        clientes.id_cliente,
                        ultimos.data_ultimo_pedido,
                        metricas.media_entre_pedidos,
                        metricas.mediana_pedidos
                    FROM clientes
                    LEFT JOIN ultimos ON ultimos.id_cliente = clientes.id_cliente
                    LEFT JOIN metricas ON metricas.id_cliente = clientes.id_cliente
                )
                UPDATE clientes
                SET inativo = CASE
                    WHEN alvos.data_ultimo_pedido IS NULL THEN 1
                    WHEN julianday(:data_corte) - julianday(alvos.data_ultimo_pedido)
                         <= :limite_dias THEN 0
                    WHEN (alvos.media_entre_pedidos IS NOT NULL
                          OR alvos.mediana_pedidos IS NOT NULL)
                         AND julianday(:data_corte) - julianday(alvos.data_ultimo_pedido)
                             <= CASE
                                    WHEN COALESCE(alvos.media_entre_pedidos, -1)
                                         > COALESCE(alvos.mediana_pedidos, -1)
                                    THEN alvos.media_entre_pedidos
                                    ELSE alvos.mediana_pedidos
                                END + :tolerancia_dias THEN 0
                    ELSE 1
                END
                FROM alvos
                WHERE clientes.id_cliente = alvos.id_cliente
                """
            ),
            {
                "data_corte": DATA_CORTE,
                "limite_dias": LIMITE_DIAS,
                "tolerancia_dias": TOLERANCIA_DIAS,
            },
        )


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

    garantir_coluna_inativo(args.banco)
    print(
        "Coluna 'inativo' atualizada com base na data de corte "
        f"{DATA_CORTE}, limite de {LIMITE_DIAS} dias e tolerância de "
        f"{TOLERANCIA_DIAS} dias."
    )


if __name__ == "__main__":
    main()
