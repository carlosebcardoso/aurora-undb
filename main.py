#!/usr/bin/env python3
"""Ponto de entrada para executar consultas no banco SQLite do projeto."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


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
        linhas = resultado
        print(" | ".join(colunas))
        print("-+-".join("-" * len(coluna) for coluna in colunas))
        for linha in linhas:
            print(" | ".join("" if valor is None else str(valor) for valor in linha))
        print(f"\n{len(linhas)} linha(s).")


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
