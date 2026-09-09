#!/usr/bin/env python3
"""Adiciona e atualiza a marcação de clientes inativos."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text


DATA_CORTE = "2026-06-30"
LIMITE_DIAS = 180


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
                UPDATE clientes
                SET inativo = CASE
                    WHEN id_cliente IN (
                        SELECT DISTINCT id_cliente
                        FROM pedidos
                        WHERE data_pedido IS NOT NULL
                          AND julianday(:data_corte) - julianday(data_pedido)
                              BETWEEN 0 AND :limite_dias
                    ) THEN 0
                    ELSE 1
                END
                """
            ),
            {
                "data_corte": DATA_CORTE,
                "limite_dias": LIMITE_DIAS,
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
        f"{DATA_CORTE}: clientes sem compra nos últimos {LIMITE_DIAS} dias "
        "marcados como inativos."
    )


if __name__ == "__main__":
    main()
