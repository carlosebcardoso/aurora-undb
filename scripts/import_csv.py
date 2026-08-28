#!/usr/bin/env python3
"""Importa arquivos CSV de uma pasta para tabelas SQLite."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Iterable


def identificador_seguro(valor: str, padrao: str) -> str:
    """Converte um nome externo em um identificador SQLite previsível."""
    valor = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    valor = re.sub(r"\W+", "_", valor, flags=re.ASCII).strip("_").lower()
    if not valor:
        valor = padrao
    if valor[0].isdigit():
        valor = f"_{valor}"
    return valor


def nomes_de_colunas(cabecalho: Iterable[str]) -> list[str]:
    """Normaliza cabeçalhos e garante que eles sejam únicos."""
    usados: set[str] = set()
    nomes: list[str] = []
    for posicao, coluna in enumerate(cabecalho, start=1):
        base = identificador_seguro(coluna.strip(), f"coluna_{posicao}")
        nome = base
        sufixo = 2
        while nome in usados:
            nome = f"{base}_{sufixo}"
            sufixo += 1
        usados.add(nome)
        nomes.append(nome)
    return nomes


def tabela_existe(conexao: sqlite3.Connection, tabela: str) -> bool:
    cursor = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (tabela,),
    )
    return cursor.fetchone() is not None


def importar_csv(conexao: sqlite3.Connection, arquivo: Path) -> str:
    tabela = identificador_seguro(arquivo.stem, "tabela")
    if tabela_existe(conexao, tabela):
        return f"IGNORADO: tabela '{tabela}' já existe"

    with arquivo.open("r", encoding="utf-8-sig", newline="") as stream:
        leitor = csv.reader(stream)
        try:
            cabecalho = next(leitor)
        except StopIteration:
            return f"IGNORADO: '{arquivo.name}' está vazio"

        colunas = nomes_de_colunas(cabecalho)
        if not colunas:
            return f"IGNORADO: '{arquivo.name}' não possui colunas"

        definicao = ", ".join(f'"{coluna}" TEXT' for coluna in colunas)
        conexao.execute(f'CREATE TABLE "{tabela}" ({definicao})')

        placeholders = ", ".join("?" for _ in colunas)
        comando = f'INSERT INTO "{tabela}" VALUES ({placeholders})'
        linhas = (
            (linha[: len(colunas)] + [""] * len(colunas))[: len(colunas)]
            for linha in leitor
        )
        conexao.executemany(comando, (linha for linha in linhas))

    return f"CRIADO: tabela '{tabela}'"


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pasta",
        type=Path,
        default=Path("dados"),
        help="pasta com os arquivos CSV (padrão: dados)",
    )
    parser.add_argument(
        "--banco",
        type=Path,
        default=Path("dados.sqlite3"),
        help="arquivo SQLite de destino (padrão: dados.sqlite3)",
    )
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    if not args.pasta.is_dir():
        raise SystemExit(f"A pasta não existe: {args.pasta}")

    args.banco.parent.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(args.pasta.glob("*.csv"))
    if not arquivos:
        print(f"Nenhum arquivo CSV encontrado em '{args.pasta}'.")
        return

    with sqlite3.connect(args.banco) as conexao:
        for arquivo in arquivos:
            try:
                print(importar_csv(conexao, arquivo))
            except csv.Error as erro:
                print(f"ERRO: '{arquivo.name}': CSV inválido ({erro})")


if __name__ == "__main__":
    main()
