#!/usr/bin/env python3
"""Conta pedidos com data fora do período definido."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
import re

from sqlalchemy import create_engine, text

# Permite executar diretamente: python scripts/pedidos_fora_periodo.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Pedidos


DATA_INICIAL = date(2023, 7, 1)
DATA_FINAL = date(2026, 6, 30)
REGEX_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REGEX_ANO_MES = re.compile(r"^\d{4}-\d{2}$")


def converter_data(valor: object, campo: str) -> date | None:
    """Valida uma data ISO completa ou um ano/mês e retorna uma data comparável."""
    if valor is None or str(valor).strip() == "":
        return None
    texto = str(valor).strip()
    regex = REGEX_DATA if campo == "data_pedido" else REGEX_ANO_MES
    if not regex.fullmatch(texto):
        raise ValueError("formato inválido")
    try:
        if campo == "ano_mes":
            ano, mes = (int(parte) for parte in texto.split("-"))
            return date(ano, mes, 1)
        return date.fromisoformat(texto)
    except ValueError as erro:
        raise ValueError("data inexistente") from erro


def analisar_datas(banco: Path) -> tuple[dict[str, dict[str, int]], list[tuple[str, object]]]:
    resultado = {
        "data_pedido": {"fora_periodo": 0, "invalidas": 0},
        "ano_mes": {"fora_periodo": 0, "invalidas": 0},
    }
    pedidos_fora_periodo: list[tuple[str, object]] = []
    engine = create_engine(f"sqlite:///{banco}")
    with engine.connect() as conexao:
        for campo, tabela in (("data_pedido", "pedidos"), ("ano_mes", "interacoes")):
            colunas = "id_pedido, data_pedido" if campo == "data_pedido" else campo
            registros = conexao.execute(text(f"SELECT {colunas} FROM {tabela}"))
            for registro in registros:
                id_pedido = registro[0] if campo == "data_pedido" else None
                valor = registro[1] if campo == "data_pedido" else registro[0]
                try:
                    data = converter_data(valor, campo)
                except ValueError:
                    resultado[campo]["invalidas"] += 1
                    continue
                if data is not None and not DATA_INICIAL <= data <= DATA_FINAL:
                    resultado[campo]["fora_periodo"] += 1
                    if campo == "data_pedido":
                        pedidos_fora_periodo.append((str(id_pedido), valor))
    return resultado, pedidos_fora_periodo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco", type=Path, default=Path("dados.sqlite3"),
        help="arquivo SQLite (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")

    resultado, pedidos_fora_periodo = analisar_datas(args.banco)
    print("Pedidos fora do período de 01/07/2023 a 30/06/2026")
    print("=" * 52)
    for campo, valores in resultado.items():
        print(f"\n{campo}")
        print(f"  Fora do período: {valores['fora_periodo']}")
        print(f"  Datas inválidas: {valores['invalidas']}")

    print("\nPedidos fora do período")
    print("-" * 24)
    if not pedidos_fora_periodo:
        print("Nenhum pedido encontrado.")
    else:
        print(f"{'id_pedido':<15} data_pedido")
        for id_pedido, data in pedidos_fora_periodo:
            print(f"{id_pedido:<15} {data}")


if __name__ == "__main__":
    main()
