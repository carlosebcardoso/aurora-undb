#!/usr/bin/env python3
"""Converte os CSVs em uma base SQLite limpa e pronta para análise."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, Float, Integer, String, create_engine, insert, inspect
from sqlalchemy.orm import Session

# Permite executar diretamente a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Base, Clientes, Interacoes, PedidoItens, Pedidos
from scripts.limpeza import DATAS_SENTINELA, UF_PARA_SIGLA, normalizar_texto, normalizar_uf


TAMANHO_LOTE = 1000


def converter_valor(valor: str, tipo: Any, tabela: str, coluna: str, linha: int) -> Any:
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
            f"{tabela}.{coluna}, linha {linha}: '{valor}' inválido ({erro})"
        ) from erro


def inserir_em_lotes(session: Session, modelo: type[Base], registros: list[dict[str, Any]]) -> None:
    for inicio in range(0, len(registros), TAMANHO_LOTE):
        session.execute(insert(modelo), registros[inicio : inicio + TAMANHO_LOTE])


def colunas_do_csv(modelo: type[Base]) -> list[str]:
    return [coluna.name for coluna in modelo.__table__.columns if coluna.autoincrement is not True]


def validar_cabecalho(cabecalho: list[str], esperadas: list[str], arquivo: Path) -> None:
    if set(cabecalho) != set(esperadas) or len(cabecalho) != len(set(cabecalho)):
        faltantes = sorted(set(esperadas) - set(cabecalho))
        extras = sorted(set(cabecalho) - set(esperadas))
        detalhes = []
        if faltantes:
            detalhes.append(f"faltam: {', '.join(faltantes)}")
        if extras:
            detalhes.append(f"extras: {', '.join(extras)}")
        raise ValueError(f"'{arquivo.name}': cabeçalho incompatível ({'; '.join(detalhes)})")


def ler_registros(arquivo: Path, modelo: type[Base]) -> tuple[list[dict[str, Any]], int]:
    colunas_model = {coluna.name: coluna for coluna in modelo.__table__.columns}
    esperadas = colunas_do_csv(modelo)
    colunas_ignoradas = ["optout"] if modelo is Clientes else []
    colunas_entrada = esperadas + colunas_ignoradas
    registros = []
    optouts_removidos = 0
    with arquivo.open("r", encoding="utf-8-sig", newline="") as stream:
        leitor = csv.DictReader(stream)
        if leitor.fieldnames is None:
            return registros, optouts_removidos
        cabecalho = [campo.strip() for campo in leitor.fieldnames]
        validar_cabecalho(cabecalho, colunas_entrada, arquivo)
        for numero_linha, registro in enumerate(leitor, start=2):
            if None in registro:
                raise ValueError(f"'{arquivo.name}', linha {numero_linha}: valores extras")
            if modelo is Clientes and registro["optout"].strip().casefold() in {"true", "t", "sim", "s", "1"}:
                optouts_removidos += 1
                continue
            valores = {
                coluna: converter_valor(registro[coluna], colunas_model[coluna].type, modelo.__tablename__, coluna, numero_linha)
                for coluna in esperadas
            }
            if modelo is Clientes:
                if valores["uf"] is not None:
                    valores["uf"] = UF_PARA_SIGLA.get(normalizar_uf(valores["uf"]), valores["uf"])
                for campo in ("cidade", "canal_aquisicao", "tier_clube"):
                    if valores[campo] is not None:
                        valores[campo] = normalizar_texto(valores[campo])
            elif modelo is Interacoes and valores["motivo_sac_principal"] is not None:
                valores["motivo_sac_principal"] = normalizar_texto(valores["motivo_sac_principal"])
            registros.append(valores)
    return registros, optouts_removidos


def ler_pedidos(arquivo: Path, ids_clientes_validos: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """Separa o CSV bruto em pedidos únicos e seus itens."""
    tipos_pedido = {coluna.name: coluna.type for coluna in Pedidos.__table__.columns}
    tipos_item = {coluna.name: coluna.type for coluna in PedidoItens.__table__.columns}
    campos_pedido = ["id_pedido", "id_cliente", "data_pedido", "canal", "cupom_utilizado", "prazo_entrega_dias", "atraso_entrega_dias"]
    campos_item = ["categoria", "sku", "quantidade", "valor_unitario", "valor_desconto", "margem_bruta_pct"]
    esperadas = campos_pedido + campos_item
    grupos: dict[str, dict[str, Any]] = {}
    with arquivo.open("r", encoding="utf-8-sig", newline="") as stream:
        leitor = csv.DictReader(stream)
        if leitor.fieldnames is None:
            return [], [], 0
        validar_cabecalho([campo.strip() for campo in leitor.fieldnames], esperadas, arquivo)
        for numero_linha, registro in enumerate(leitor, start=2):
            if None in registro:
                raise ValueError(f"'{arquivo.name}', linha {numero_linha}: valores extras")
            id_pedido = registro["id_pedido"].strip()
            pedido = {
                campo: converter_valor(registro[campo], tipos_pedido[campo], "pedidos", campo, numero_linha)
                for campo in campos_pedido
            }
            item = {"id_pedido": id_pedido}
            item.update({
                campo: converter_valor(registro[campo], tipos_item[campo], "pedido_itens", campo, numero_linha)
                for campo in campos_item
            })
            pedido["id_pedido"] = id_pedido
            pedido["canal"] = normalizar_texto(pedido["canal"]) if pedido["canal"] else None
            if pedido["atraso_entrega_dias"] == 0:
                pedido["atraso_entrega_dias"] = None
            item["categoria"] = normalizar_texto(item["categoria"]) if item["categoria"] else None
            grupo = grupos.setdefault(id_pedido, {"pedido": pedido, "itens": [], "datas_validas": []})
            if pedido["data_pedido"] is not None and pedido["data_pedido"] not in DATAS_SENTINELA:
                grupo["datas_validas"].append(pedido["data_pedido"])
            grupo["itens"].append(item)

    pedidos = []
    itens = []
    removidos_sem_data = 0
    removidos_optout = 0
    for grupo in grupos.values():
        pedido = grupo["pedido"]
        if pedido["id_cliente"] not in ids_clientes_validos:
            removidos_optout += 1
            continue
        datas_validas = grupo["datas_validas"]
        # As linhas repetidas podem ter datas diferentes; usa uma data válida
        # de qualquer linha do mesmo id antes de descartar/substituir.
        if pedido["data_pedido"] in DATAS_SENTINELA:
            if not datas_validas:
                removidos_sem_data += 1
                continue
            pedido["data_pedido"] = datas_validas[0]
        pedidos.append(pedido)
        itens.extend(grupo["itens"])
    return pedidos, itens, removidos_sem_data, removidos_optout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, default=Path("dados"))
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    parser.add_argument("--reiniciar", action="store_true", help="recria a base e converte os CSVs novamente")
    args = parser.parse_args()
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
    existentes = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        try:
            ids_clientes_validos: set[str] = set()
            if "clientes" not in existentes and "clientes" in arquivos:
                registros, clientes_optout = ler_registros(arquivos["clientes"], Clientes)
                inserir_em_lotes(session, Clientes, registros)
                ids_clientes_validos = {registro["id_cliente"] for registro in registros}
                print(f"CARREGADO: clientes ({len(registros)} linha(s))")
                print(f"CLIENTES REMOVIDOS POR OPTOUT: {clientes_optout}")
            if "interacoes" not in existentes and "interacoes" in arquivos:
                registros, _ = ler_registros(arquivos["interacoes"], Interacoes)
                total_interacoes = len(registros)
                registros = [registro for registro in registros if registro["id_cliente"] in ids_clientes_validos]
                inserir_em_lotes(session, Interacoes, registros)
                print(f"CARREGADO: interacoes ({len(registros)} linha(s))")
                print(f"INTERAÇÕES REMOVIDAS POR OPTOUT: {total_interacoes - len(registros)}")
            if "pedidos" not in existentes and "pedidos" in arquivos:
                pedidos, itens, removidos_sem_data, pedidos_optout = ler_pedidos(arquivos["pedidos"], ids_clientes_validos)
                inserir_em_lotes(session, Pedidos, pedidos)
                inserir_em_lotes(session, PedidoItens, itens)
                print(f"CARREGADO: pedidos ({len(pedidos)} linha(s))")
                print(f"CARREGADO: pedido_itens ({len(itens)} linha(s))")
                print(f"PEDIDOS REMOVIDOS POR OPTOUT: {pedidos_optout}")
                if removidos_sem_data:
                    print(f"PEDIDOS REMOVIDOS SEM DATA VÁLIDA: {removidos_sem_data}")
            session.commit()
        except (csv.Error, ValueError) as erro:
            session.rollback()
            raise SystemExit(f"Erro na conversão: {erro}") from erro


if __name__ == "__main__":
    main()
