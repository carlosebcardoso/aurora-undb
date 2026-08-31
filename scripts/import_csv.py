#!/usr/bin/env python3
"""Importa os CSVs das tabelas fixas do projeto usando SQLAlchemy."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, Float, Integer, String, create_engine, insert, inspect
from sqlalchemy.orm import Session

# Permite executar tanto `python -m scripts.import_csv` quanto
# `python scripts/import_csv.py` a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Base, Clientes, Interacoes, Pedidos


MODELOS = {"clientes": Clientes, "interacoes": Interacoes, "pedidos": Pedidos}


def converter_valor(valor: str, tipo: Any, tabela: str, coluna: str, linha: int) -> Any:
    """Converte um valor textual para o tipo SQLAlchemy da coluna."""
    valor = valor.strip()
    if not valor:
        return None
    try:
        if isinstance(tipo, Boolean):
            normalizado = valor.casefold()
            if normalizado in {"true", "t", "sim", "s", "1"}:
                return True
            if normalizado in {"false", "f", "nao", "não", "n", "0"}:
                return False
            raise ValueError("use True ou False")
        if isinstance(tipo, Integer):
            return int(valor)
        if isinstance(tipo, Float):
            return float(valor.replace(",", "."))
        if isinstance(tipo, Date):
            return date.fromisoformat(valor)
        if isinstance(tipo, String):
            return valor
        return valor
    except ValueError as erro:
        raise ValueError(
            f"{tabela}.{coluna}, linha {linha}: '{valor}' inválido para {tipo} ({erro})"
        ) from erro


def importar_csv(session: Session, arquivo: Path, modelo: type[Base]) -> str:
    """Lê um CSV e insere seus registros usando o model ORM correspondente."""
    tabela = modelo.__table__

    with arquivo.open("r", encoding="utf-8-sig", newline="") as stream:
        leitor = csv.DictReader(stream)
        if leitor.fieldnames is None:
            return f"IGNORADO: '{arquivo.name}' está vazio"

        colunas_csv = [coluna.strip() for coluna in leitor.fieldnames]
        colunas_model = [coluna.name for coluna in tabela.columns]
        geradas = {
            coluna.name for coluna in tabela.columns if coluna.autoincrement is True
        }
        esperadas_csv = set(colunas_model) - geradas
        if set(colunas_csv) != esperadas_csv or len(colunas_csv) != len(set(colunas_csv)):
            faltantes = sorted(esperadas_csv - set(colunas_csv))
            desconhecidas = sorted(set(colunas_csv) - set(colunas_model))
            detalhes = []
            if faltantes:
                detalhes.append(f"faltam no CSV: {', '.join(faltantes)}")
            if desconhecidas:
                detalhes.append(f"não estão no model: {', '.join(desconhecidas)}")
            raise ValueError(f"colunas incompatíveis ({'; '.join(detalhes)})")

        colunas = {coluna.name: coluna for coluna in tabela.columns}
        colunas_csv_model = [coluna for coluna in colunas_model if coluna not in geradas]
        lote = []
        quantidade = 0
        for numero_linha, registro in enumerate(leitor, start=2):
            if None in registro:
                raise ValueError(f"linha {numero_linha}: quantidade de valores diferente do cabeçalho")
            valores = {
                coluna: converter_valor(registro[coluna], colunas[coluna].type, tabela.name, coluna, numero_linha)
                for coluna in colunas_csv_model
            }
            lote.append(valores)
            if len(lote) == 1000:
                session.execute(insert(modelo), lote)
                quantidade += len(lote)
                lote = []
        if lote:
            session.execute(insert(modelo), lote)
            quantidade += len(lote)
    return f"CARREGADO: tabela '{tabela.name}' ({quantidade} linha(s))"


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, default=Path("dados"))
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    parser.add_argument(
        "--reiniciar", action="store_true",
        help="apaga as tabelas fixas e carrega os CSVs novamente",
    )
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    if not args.pasta.is_dir():
        raise SystemExit(f"A pasta não existe: {args.pasta}")
    arquivos = {arquivo.stem: arquivo for arquivo in args.pasta.glob("*.csv")}
    if not arquivos:
        print(f"Nenhum arquivo CSV encontrado em '{args.pasta}'.")
        return

    args.banco.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{args.banco}")
    if args.reiniciar:
        Base.metadata.drop_all(engine)
    tabelas_existentes = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        try:
            for nome, modelo in MODELOS.items():
                arquivo = arquivos.get(nome)
                if arquivo is None:
                    print(f"IGNORADO: CSV não encontrado para '{nome}'")
                    continue
                if nome in tabelas_existentes:
                    print(f"IGNORADO: tabela '{nome}' já existe")
                    continue
                print(importar_csv(session, arquivo, modelo))
            session.commit()
        except (csv.Error, ValueError) as erro:
            session.rollback()
            raise SystemExit(f"Erro na importação: {erro}") from erro


if __name__ == "__main__":
    main()
