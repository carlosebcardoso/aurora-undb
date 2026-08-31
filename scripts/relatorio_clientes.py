#!/usr/bin/env python3
"""Exibe quantidade e percentual dos clientes por diferentes dimensões."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, literal, select
from sqlalchemy.orm import Session

# Permite executar diretamente: python scripts/relatorio_clientes.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Clientes


DIMENSOES = (
    ("Estado", Clientes.uf),
    ("Faixa etária", Clientes.faixa_etaria),
    ("Canal de aquisição", Clientes.canal_aquisicao),
)


def nome_do_grupo(coluna):
    """Converte NULL e texto vazio em um grupo legível no relatório."""
    return func.coalesce(func.nullif(func.trim(coluna), ""), literal("NÃO INFORMADO"))


def imprimir_grupo(titulo: str, linhas: list[tuple[str, int]], total: int) -> None:
    print(f"\n{titulo}")
    print("-" * len(titulo))
    print(f"{'Grupo':<30} {'Quantidade':>12} {'Percentual':>12}")
    print(f"{'-' * 30} {'-' * 12} {'-' * 12}")
    for grupo, quantidade in linhas:
        percentual = quantidade / total * 100 if total else 0
        print(f"{grupo:<30} {quantidade:>12} {percentual:>11.2f}%")
    print(f"{'TOTAL':<30} {total:>12} {'100.00%' if total else '0.00%':>12}")


def gerar_relatorio(banco: Path) -> None:
    engine = create_engine(f"sqlite:///{banco}")
    with Session(engine) as session:
        total = session.scalar(select(func.count(Clientes.id_cliente))) or 0
        for titulo, coluna in DIMENSOES:
            grupo = nome_do_grupo(coluna).label("grupo")
            consulta = (
                select(grupo, func.count(Clientes.id_cliente).label("quantidade"))
                .group_by(grupo)
                .order_by(func.count(Clientes.id_cliente).desc(), grupo)
            )
            linhas = [(str(nome), quantidade) for nome, quantidade in session.execute(consulta)]
            imprimir_grupo(titulo, linhas, total)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco", type=Path, default=Path("dados.sqlite3"),
        help="arquivo SQLite (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    gerar_relatorio(args.banco)


if __name__ == "__main__":
    main()
