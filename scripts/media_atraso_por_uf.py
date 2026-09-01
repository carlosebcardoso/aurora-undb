#!/usr/bin/env python3
"""Exibe a média de atraso de entrega por UF do cliente."""

from __future__ import annotations

import argparse
import sys
import statistics
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Permite executar diretamente: python scripts/media_atraso_por_uf.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Clientes, Pedidos


def imprimir_media_atraso(banco: Path) -> None:
    engine = create_engine(f"sqlite:///{banco}")
    with Session(engine) as session:
        consulta = (
            select(Clientes.uf, Pedidos.atraso_entrega_dias)
            .join(Pedidos, Pedidos.id_cliente == Clientes.id_cliente)
            .where(Pedidos.atraso_entrega_dias > 0)
            .order_by(Clientes.uf)
        )
        atrasos_por_uf: defaultdict[str | None, list[float]] = defaultdict(list)
        for uf, atraso in session.execute(consulta):
            atrasos_por_uf[uf].append(float(atraso))

    print("Média de atraso de entrega por UF")
    print("=" * 33)
    print(f"{'UF':<15} {'Média (dias)':>14}")
    print(f"{'-' * 15} {'-' * 14}")
    medias_por_uf = {}
    for uf, atrasos in atrasos_por_uf.items():
        media = statistics.mean(atrasos)
        medias_por_uf[uf] = media
        print(f"{uf or 'NÃO INFORMADO':<15} {media:>14.2f}")

    desvio_das_medias = statistics.pstdev(medias_por_uf.values()) if medias_por_uf else 0
    print(f"\nDesvio padrão das médias das UFs: {desvio_das_medias:.2f} dias")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco", type=Path, default=Path("dados.sqlite3"),
        help="arquivo SQLite (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    imprimir_media_atraso(args.banco)


if __name__ == "__main__":
    main()
