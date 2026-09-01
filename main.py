#!/usr/bin/env python3
"""Ponto de entrada para executar consultas no banco SQLite do projeto."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def imprimir_tabela(colunas: list[str], linhas: list[sqlite3.Row]) -> None:
    """Imprime resultados tabulares com larguras calculadas por coluna."""
    valores = [
        ["" if linha[indice] is None else str(linha[indice]) for indice in range(len(colunas))]
        for linha in linhas
    ]
    larguras = [
        max([len(coluna)] + [len(linha[indice]) for linha in valores])
        for indice, coluna in enumerate(colunas)
    ]

    cabecalho = " | ".join(coluna.ljust(larguras[indice]) for indice, coluna in enumerate(colunas))
    separador = "-+-".join("-" * largura for largura in larguras)
    print(cabecalho)
    print(separador)
    for linha in valores:
        print(" | ".join(valor.ljust(larguras[indice]) for indice, valor in enumerate(linha)))


def executar_consulta(banco: Path, arquivo_sql: Path) -> None:
    """Abre o banco, executa o script SQL e imprime os resultados."""
    if not banco.exists():
        raise SystemExit(
            f"Banco não encontrado: {banco}. Execute primeiro o importador de CSV."
        )
    if not arquivo_sql.is_file():
        raise SystemExit(f"Arquivo de consulta não encontrado: {arquivo_sql}")

    with sqlite3.connect(banco) as conexao:
        conexao.row_factory = sqlite3.Row
        cursor = conexao.cursor()
        instrucoes: list[str] = []
        acumulado = ""
        for linha in arquivo_sql.read_text(encoding="utf-8").splitlines(keepends=True):
            acumulado += linha
            if sqlite3.complete_statement(acumulado):
                if acumulado.strip():
                    instrucoes.append(acumulado)
                acumulado = ""
        if acumulado.strip():
            instrucoes.append(acumulado)

        resultado: list[sqlite3.Row] = []
        descricao: list[tuple] | None = None
        for instrucao in instrucoes:
            cursor.execute(instrucao)
            if cursor.description is not None:
                descricao = cursor.description
                resultado = cursor.fetchall()

        if descricao is None:
            print("Consulta executada com sucesso (sem resultado para exibir).")
            return

        colunas = [coluna[0] for coluna in descricao]
        imprimir_tabela(colunas, resultado)
        print(f"\n{len(resultado)} linha(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco",
        type=Path,
        default=Path("dados.sqlite3"),
        help="arquivo SQLite (padrão: dados.sqlite3)",
    )
    parser.add_argument(
        "--consulta",
        type=Path,
        required=True,
        help="arquivo .sql dentro da pasta consultas/ ou outro caminho",
    )
    args = parser.parse_args()
    executar_consulta(args.banco, args.consulta)


if __name__ == "__main__":
    main()
