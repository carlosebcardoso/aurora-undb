#!/usr/bin/env python3
"""Normaliza pedidos, separando seus itens e criando as chaves relacionais."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def migrar(banco: Path) -> None:
    engine = create_engine(f"sqlite:///{banco}")
    with engine.connect() as conexao:
        tabelas = set(inspect(conexao).get_table_names())
        obrigatorias = {"clientes", "pedidos"}
        ausentes = obrigatorias - tabelas
        if ausentes:
            raise RuntimeError(f"Tabelas ausentes: {', '.join(sorted(ausentes))}")
        if "pedido_itens" in tabelas:
            raise RuntimeError("A tabela 'pedido_itens' já existe; migração interrompida")

        conexao.rollback()
        conexao.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conexao.commit()
        transacao = conexao.begin()
        try:
            # Preserva cada linha original de pedidos como um item.
            conexao.execute(text("""
                CREATE TABLE pedido_itens_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_pedido TEXT NOT NULL,
                    categoria VARCHAR,
                    sku VARCHAR,
                    quantidade INTEGER,
                    valor_unitario FLOAT,
                    valor_desconto FLOAT,
                    margem_bruta_pct FLOAT
                )
            """))
            conexao.execute(text("""
                INSERT INTO pedido_itens_temp
                    (id_pedido, categoria, sku, quantidade, valor_unitario,
                     valor_desconto, margem_bruta_pct)
                SELECT id_pedido, categoria, sku, quantidade, valor_unitario,
                       valor_desconto, margem_bruta_pct
                FROM pedidos
            """))

            conexao.execute(text("""
                CREATE TABLE clientes_novo (
                    id_cliente VARCHAR PRIMARY KEY,
                    data_cadastro DATE,
                    data_ultima_atualizacao_cadastro DATE,
                    uf VARCHAR,
                    cidade VARCHAR,
                    faixa_etaria VARCHAR,
                    canal_aquisicao VARCHAR,
                    tier_clube VARCHAR,
                    optin_email BOOLEAN,
                    optout BOOLEAN
                )
            """))
            conexao.execute(text("""
                INSERT INTO clientes_novo
                SELECT id_cliente, data_cadastro, data_ultima_atualizacao_cadastro,
                       uf, cidade, faixa_etaria, canal_aquisicao, tier_clube,
                       optin_email, optout
                FROM clientes
            """))
            conexao.execute(text("DROP TABLE clientes"))
            conexao.execute(text("ALTER TABLE clientes_novo RENAME TO clientes"))

            # Mantém a primeira linha de cada id_pedido como registro pai.
            conexao.execute(text("""
                CREATE TABLE pedidos_novo (
                    id_pedido VARCHAR PRIMARY KEY,
                    id_cliente VARCHAR,
                    data_pedido DATE,
                    canal VARCHAR,
                    cupom_utilizado BOOLEAN,
                    prazo_entrega_dias INTEGER,
                    atraso_entrega_dias FLOAT,
                    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente)
                )
            """))
            conexao.execute(text("""
                INSERT INTO pedidos_novo
                SELECT p.id_pedido, p.id_cliente, p.data_pedido, p.canal,
                       p.cupom_utilizado, p.prazo_entrega_dias,
                       p.atraso_entrega_dias
                FROM pedidos p
                WHERE p.id IN (
                    SELECT MIN(id) FROM pedidos GROUP BY id_pedido
                )
            """))
            conexao.execute(text("DROP TABLE pedidos"))
            conexao.execute(text("ALTER TABLE pedidos_novo RENAME TO pedidos"))

            conexao.execute(text("""
                CREATE TABLE pedido_itens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_pedido VARCHAR NOT NULL,
                    categoria VARCHAR,
                    sku VARCHAR,
                    quantidade INTEGER,
                    valor_unitario FLOAT,
                    valor_desconto FLOAT,
                    margem_bruta_pct FLOAT,
                    FOREIGN KEY (id_pedido) REFERENCES pedidos (id_pedido)
                )
            """))
            conexao.execute(text("""
                INSERT INTO pedido_itens
                    (id_pedido, categoria, sku, quantidade, valor_unitario,
                     valor_desconto, margem_bruta_pct)
                SELECT id_pedido, categoria, sku, quantidade, valor_unitario,
                       valor_desconto, margem_bruta_pct
                FROM pedido_itens_temp
            """))
            conexao.execute(text("DROP TABLE pedido_itens_temp"))
            transacao.commit()
        except Exception:
            transacao.rollback()
            raise
        finally:
            conexao.exec_driver_sql("PRAGMA foreign_keys=ON")

    print("Migração concluída: pedidos, clientes e pedido_itens normalizados.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    migrar(args.banco)


if __name__ == "__main__":
    main()
