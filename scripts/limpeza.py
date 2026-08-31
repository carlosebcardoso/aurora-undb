#!/usr/bin/env python3
"""Limpa os valores de UF da tabela clientes."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Permite executar diretamente a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Clientes, Interacoes, Pedidos


# Remove marcas de acentuação depois da decomposição Unicode (NFD).
REGEX_ACENTOS = re.compile(r"[\u0300-\u036f]")
REGEX_SEPARADORES = re.compile(r"[\s._-]+")


def normalizar_uf(valor: str) -> str:
    """Padroniza caixa, acentos e separadores para comparar valores de UF."""
    valor = unicodedata.normalize("NFD", valor.casefold().strip())
    valor = REGEX_ACENTOS.sub("", valor)
    return REGEX_SEPARADORES.sub("", valor)


# As chaves são normalizadas antes da comparação. A lista cobre as 27 unidades
# federativas: os 26 estados e o Distrito Federal.
ESTADOS_BRASIL = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
    "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
    "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO",
}

UF_PARA_SIGLA = {
    **{normalizar_uf(nome): sigla for nome, sigla in ESTADOS_BRASIL.items()},
    **{sigla.casefold(): sigla for sigla in ESTADOS_BRASIL.values()},
    # Variação ortográfica solicitada para Maranhão.
    "marahao": "MA",
}

CAMPOS_TEXTO = {
    Clientes: ("cidade", "canal_aquisicao", "tier_clube"),
    Interacoes: ("motivo_sac_principal",),
    Pedidos: ("canal", "categoria"),
}

DATAS_SENTINELA = {date(1900, 1, 1), date(2099, 12, 31)}


def normalizar_texto(valor: str) -> str:
    """Converte texto para maiúsculas e remove seus acentos."""
    valor = unicodedata.normalize("NFD", valor)
    return REGEX_ACENTOS.sub("", valor).upper()


def limpar_ufs(banco: Path) -> tuple[int, Counter[str]]:
    """Corrige as UFs conhecidas e retorna alterações e valores desconhecidos."""
    engine = create_engine(f"sqlite:///{banco}")
    alteracoes = 0
    desconhecidos: Counter[str] = Counter()
    with Session(engine) as session:
        for cliente in session.scalars(select(Clientes)):
            if cliente.uf is None:
                continue
            sigla = UF_PARA_SIGLA.get(normalizar_uf(cliente.uf))
            if sigla is None:
                desconhecidos[cliente.uf] += 1
                continue
            if cliente.uf != sigla:
                cliente.uf = sigla
                alteracoes += 1
        session.commit()
    return alteracoes, desconhecidos


def limpar_campos_texto(banco: Path) -> int:
    """Padroniza os campos textuais configurados em CAMPOS_TEXTO."""
    engine = create_engine(f"sqlite:///{banco}")
    alteracoes = 0
    with Session(engine) as session:
        for modelo, campos in CAMPOS_TEXTO.items():
            for registro in session.scalars(select(modelo)):
                for campo in campos:
                    valor = getattr(registro, campo)
                    if valor is None:
                        continue
                    texto_limpo = normalizar_texto(valor)
                    if valor != texto_limpo:
                        setattr(registro, campo, texto_limpo)
                        alteracoes += 1
        session.commit()
    return alteracoes


def corrigir_datas_pedidos(banco: Path) -> tuple[int, int]:
    """Corrige datas sentinela ou remove pedidos sem nenhuma data válida."""
    engine = create_engine(f"sqlite:///{banco}")
    corrigidos = 0
    removidos = 0
    with Session(engine) as session:
        pedidos_por_id: defaultdict[str, list[Pedidos]] = defaultdict(list)
        for pedido in session.scalars(select(Pedidos)):
            pedidos_por_id[pedido.id_pedido].append(pedido)

        for id_pedido, pedidos in pedidos_por_id.items():
            datas_validas = [
                pedido.data_pedido
                for pedido in pedidos
                if pedido.data_pedido is not None
                and pedido.data_pedido not in DATAS_SENTINELA
            ]
            if not datas_validas:
                for pedido in pedidos:
                    if pedido.data_pedido in DATAS_SENTINELA:
                        session.delete(pedido)
                        removidos += 1
                continue
            data_substituta = datas_validas[0]
            for pedido in pedidos:
                if pedido.data_pedido in DATAS_SENTINELA:
                    pedido.data_pedido = data_substituta
                    corrigidos += 1
        session.commit()
    return corrigidos, removidos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--banco", type=Path, default=Path("dados.sqlite3"),
        help="arquivo SQLite que será limpo (padrão: dados.sqlite3)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")

    alteracoes, desconhecidos = limpar_ufs(args.banco)
    textos_corrigidos = limpar_campos_texto(args.banco)
    datas_corrigidas, pedidos_removidos = corrigir_datas_pedidos(args.banco)
    print(f"UFs corrigidas: {alteracoes}")
    print(f"Campos de texto corrigidos: {textos_corrigidos}")
    print(f"Datas de pedidos corrigidas: {datas_corrigidas}")
    print(f"Pedidos removidos sem outra data válida: {pedidos_removidos}")
    if desconhecidos:
        print("Valores de UF não reconhecidos (preservados):")
        for valor, quantidade in desconhecidos.most_common():
            print(f"  {valor!r}: {quantidade}")


if __name__ == "__main__":
    main()
