#!/usr/bin/env python3
"""Compara dados repetidos de pedidos agrupados pelo id_pedido."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Permite executar diretamente: python scripts/comparar_pedidos.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Pedidos


CAMPOS_COMPARADOS = (
    ("data_pedido", Pedidos.data_pedido),
    ("canal", Pedidos.canal),
    ("prazo_entrega_dias", Pedidos.prazo_entrega_dias),
    ("atraso_entrega_dias", Pedidos.atraso_entrega_dias),
    ("id_cliente", Pedidos.id_cliente),
    ("cupom_utilizado", Pedidos.cupom_utilizado),
)


def comparar_pedidos(banco: Path) -> tuple[int, int, Counter[str], int, dict[str, dict[str, set]]]:
    """Retorna o resumo e os valores divergentes de cada grupo."""
    engine = create_engine(f"sqlite:///{banco}")
    pedidos_por_id: defaultdict[str, list[tuple]] = defaultdict(list)
    colunas = [coluna for _, coluna in CAMPOS_COMPARADOS]

    with Session(engine) as session:
        consulta = select(Pedidos.id_pedido, *colunas).order_by(Pedidos.id_pedido)
        for registro in session.execute(consulta):
            pedidos_por_id[registro[0]].append(tuple(registro[1:]))

    iguais = divergentes = 0
    motivos: Counter[str] = Counter()
    grupos_repetidos = 0
    detalhes_divergentes: dict[str, dict[str, set]] = {}
    for registro_id, registros in pedidos_por_id.items():
        if len(registros) < 2:
            continue
        grupos_repetidos += 1
        diferentes = {
            nome
            for indice, (nome, _) in enumerate(CAMPOS_COMPARADOS)
            if len({registro[indice] for registro in registros}) > 1
        }
        if diferentes:
            divergentes += 1
            motivos.update(diferentes)
            detalhes_divergentes[registro_id] = {
                nome: {registro[indice] for registro in registros}
                for indice, (nome, _) in enumerate(CAMPOS_COMPARADOS)
                if nome in diferentes
            }
        else:
            iguais += 1

    return iguais, divergentes, motivos, grupos_repetidos, detalhes_divergentes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco", type=Path, default=Path("dados.sqlite3"),
        help="arquivo SQLite (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")

    iguais, divergentes, motivos, total, detalhes_divergentes = comparar_pedidos(args.banco)
    print("Comparação dos pedidos com id_pedido repetido")
    print("=" * 48)
    print(f"Grupos de id_pedido repetidos: {total}")
    print(f"Todos os campos iguais:         {iguais}")
    print(f"Algum campo diferente:          {divergentes}")

    print("\nDivergências por campo")
    print("-" * 24)
    if not motivos:
        print("Nenhuma divergência encontrada.")
    else:
        for campo, quantidade in motivos.most_common():
            print(f"{campo:<24} {quantidade:>6}")

    print("\nPedidos com divergências")
    print("-" * 25)
    if not detalhes_divergentes:
        print("Nenhum pedido divergente encontrado.")
    else:
        for id_pedido, campos in detalhes_divergentes.items():
            print(f"{id_pedido}:")
            for campo, valores in campos.items():
                valores_formatados = ", ".join(repr(valor) for valor in valores)
                print(f"  {campo}: {valores_formatados}")


if __name__ == "__main__":
    main()
