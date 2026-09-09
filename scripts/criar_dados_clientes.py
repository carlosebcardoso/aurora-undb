#!/usr/bin/env python3
"""Consolida e trata os atributos dos clientes para uso em clustering."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median, pstdev

from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import ClustersClientes, Clientes, DadosClientes, DesviosCluster, Interacoes, PedidoItens, Pedidos, ResultadosCluster


DATA_REFERENCIA_PADRAO = date(2026, 6, 30)
VERSAO_ATRIBUTOS = "v2-perfis-acionaveis"


def numero(valor, padrao=0):
    return padrao if valor is None else valor


def media_segura(valores: list[float]) -> float:
    return round(mean(valores), 2) if valores else 0.0


def mediana_segura(valores: list[float]) -> float:
    return round(median(valores), 2) if valores else 0.0


def dias_entre(inicio: date | None, fim: date) -> int:
    return max((fim - inicio).days, 0) if inicio else 0


def criar_dados_clientes(banco: Path, data_referencia: date) -> int:
    engine = create_engine(f"sqlite:///{banco}")
    agora = datetime.now().replace(microsecond=0)
    # As duas tabelas são derivadas e podem ser recriadas com segurança. Isso
    # também aplica mudanças de schema, como a remoção da coluna inativo.
    ClustersClientes.__table__.drop(engine, checkfirst=True)
    ResultadosCluster.__table__.drop(engine, checkfirst=True)
    DesviosCluster.__table__.drop(engine, checkfirst=True)
    DadosClientes.__table__.drop(engine, checkfirst=True)
    DadosClientes.__table__.create(engine)
    ClustersClientes.__table__.create(engine)
    ResultadosCluster.__table__.create(engine)
    DesviosCluster.__table__.create(engine)

    with Session(engine) as session:
        # inativo é uma coluna adicionada pelo script de limpeza e ainda não
        # faz parte do modelo de entrada de clientes.
        clientes = session.execute(text("""
            SELECT id_cliente, uf, faixa_etaria, canal_aquisicao, tier_clube,
                   optin_email, data_cadastro
            FROM clientes
            WHERE COALESCE(inativo, 0) = 1
              AND id_cliente IN (
                  SELECT id_cliente
                  FROM pedidos
                  WHERE data_pedido IS NOT NULL
                    AND data_pedido <= :data_referencia
                  GROUP BY id_cliente
                  HAVING COUNT(*) >= 2
              )
            ORDER BY id_cliente
        """), {"data_referencia": data_referencia.isoformat()}).all()
        if not clientes:
            raise RuntimeError("A tabela clientes não possui registros.")

        pedidos_por_cliente = defaultdict(list)
        pedido_info = {}
        for pedido in session.execute(
            select(
                Pedidos.id_pedido, Pedidos.id_cliente, Pedidos.data_pedido,
                Pedidos.cupom_utilizado, Pedidos.prazo_entrega_dias,
                Pedidos.atraso_entrega_dias,
            ).where(
                Pedidos.data_pedido.is_not(None),
                Pedidos.data_pedido <= data_referencia,
            )
        ):
            pedido_info[pedido.id_pedido] = {
                "id_cliente": pedido.id_cliente,
                "data": pedido.data_pedido,
                "cupom": bool(pedido.cupom_utilizado),
                "prazo": pedido.prazo_entrega_dias,
                "atraso": numero(pedido.atraso_entrega_dias),
                "valor": 0.0,
                "desconto": 0.0,
                "quantidade": 0,
                "skus": set(),
                "categorias": set(),
                "margens": [],
            }
            pedidos_por_cliente[pedido.id_cliente].append(pedido.id_pedido)

        for item in session.execute(
            select(
                PedidoItens.id_pedido, PedidoItens.sku, PedidoItens.categoria,
                PedidoItens.quantidade, PedidoItens.valor_unitario,
                PedidoItens.valor_desconto, PedidoItens.margem_bruta_pct,
            ).join(Pedidos, Pedidos.id_pedido == PedidoItens.id_pedido).where(
                Pedidos.data_pedido.is_not(None),
                Pedidos.data_pedido <= data_referencia,
            )
        ):
            pedido = pedido_info.get(item.id_pedido)
            if pedido is None:
                continue
            quantidade = numero(item.quantidade)
            unitario = numero(item.valor_unitario)
            desconto = numero(item.valor_desconto)
            # valor_desconto é tratado como desconto total do item, não unitário.
            pedido["valor"] += quantidade * unitario - desconto
            pedido["desconto"] += desconto
            pedido["quantidade"] += quantidade
            if item.sku:
                pedido["skus"].add(item.sku)
            if item.categoria:
                pedido["categorias"].add(item.categoria)
            if item.margem_bruta_pct is not None:
                pedido["margens"].append(item.margem_bruta_pct)

        interacoes_por_cliente = defaultdict(list)
        for interacao in session.scalars(select(Interacoes).order_by(Interacoes.id)):
            interacoes_por_cliente[interacao.id_cliente].append(interacao)

        registros = []
        for cliente in clientes:
            data_cadastro = (
                date.fromisoformat(cliente.data_cadastro)
                if isinstance(cliente.data_cadastro, str)
                else cliente.data_cadastro
            )
            ids_pedidos = pedidos_por_cliente[cliente.id_cliente]
            pedidos = [pedido_info[id_pedido] for id_pedido in ids_pedidos]
            pedidos.sort(key=lambda pedido: pedido["data"])
            datas = [pedido["data"] for pedido in pedidos]
            intervalos = [
                (atual - anterior).days
                for anterior, atual in zip(datas, datas[1:])
            ]
            valores = [pedido["valor"] for pedido in pedidos]
            descontos = [pedido["desconto"] for pedido in pedidos]
            prazos = [pedido["prazo"] for pedido in pedidos if pedido["prazo"] is not None]
            atrasos = [pedido["atraso"] for pedido in pedidos]
            margens = [margem for pedido in pedidos for margem in pedido["margens"]]
            ids_interacoes = interacoes_por_cliente[cliente.id_cliente]
            quantidade_campanhas = sum(numero(i.campanhas_enviadas) for i in ids_interacoes)
            quantidade_abertas = sum(numero(i.campanhas_abertas) for i in ids_interacoes)
            quantidade_cliques = sum(numero(i.cliques) for i in ids_interacoes)
            quantidade_tickets = sum(numero(i.tickets_sac) for i in ids_interacoes)
            tickets_resolvidos = sum(
                numero(i.tickets_sac) for i in ids_interacoes if i.ticket_resolvido
            )
            ultimo_pedido = datas[-1] if datas else None
            primeiro_pedido = datas[0] if datas else None
            quantidade_pedidos = len(pedidos)
            dias_cadastro = dias_entre(data_cadastro, data_referencia)

            registros.append({
                "id_cliente": cliente.id_cliente,
                "uf": cliente.uf or "NAO_INFORMADO",
                "faixa_etaria": cliente.faixa_etaria or "NAO_INFORMADO",
                "canal_aquisicao": cliente.canal_aquisicao or "NAO_INFORMADO",
                "tier_clube": cliente.tier_clube or "NAO_INFORMADO",
                "optin_email": cliente.optin_email,
                "data_cadastro": data_cadastro,
                "dias_desde_cadastro": dias_cadastro,
                "quantidade_pedidos": quantidade_pedidos,
                "data_primeiro_pedido": primeiro_pedido,
                "data_ultimo_pedido": ultimo_pedido,
                "dias_desde_ultimo_pedido": dias_entre(ultimo_pedido, data_referencia),
                "intervalo_medio_pedidos": media_segura(intervalos),
                "intervalo_mediano_pedidos": mediana_segura(intervalos),
                "intervalo_minimo_pedidos": min(intervalos, default=0),
                "intervalo_maximo_pedidos": max(intervalos, default=0),
                "desvio_intervalo_pedidos": round(pstdev(intervalos), 2) if len(intervalos) > 1 else 0.0,
                "quantidade_itens": sum(pedido["quantidade"] for pedido in pedidos),
                "quantidade_skus_distintos": len(set().union(*(p["skus"] for p in pedidos))) if pedidos else 0,
                "quantidade_categorias_distintas": len(set().union(*(p["categorias"] for p in pedidos))) if pedidos else 0,
                "valor_total_compras": round(sum(valores), 2),
                "ticket_medio": media_segura(valores),
                "ticket_mediano": mediana_segura(valores),
                "desconto_total": round(sum(descontos), 2),
                "percentual_pedidos_com_desconto": round(sum(d > 0 for d in descontos) / quantidade_pedidos, 4) if pedidos else 0.0,
                "percentual_pedidos_com_cupom": round(sum(pedido["cupom"] for pedido in pedidos) / quantidade_pedidos, 4) if pedidos else 0.0,
                "itens_por_pedido": round(sum(pedido["quantidade"] for pedido in pedidos) / quantidade_pedidos, 4) if pedidos else 0.0,
                "margem_media": media_segura(margens),
                "quantidade_pedidos_com_cupom": sum(pedido["cupom"] for pedido in pedidos),
                "prazo_medio_entrega": media_segura(prazos),
                "atraso_medio_entrega": media_segura(atrasos),
                "maior_atraso_entrega": max(atrasos, default=0),
                "pedidos_com_atraso": sum(atraso > 0 for atraso in atrasos),
                "percentual_pedidos_com_atraso": round(sum(atraso > 0 for atraso in atrasos) / quantidade_pedidos, 4) if pedidos else 0.0,
                "possui_interacao": bool(ids_interacoes),
                "meses_com_interacao": len(ids_interacoes),
                "campanhas_enviadas_total": quantidade_campanhas,
                "campanhas_reativacao_total": sum(numero(i.campanhas_reativacao_recebidas) for i in ids_interacoes),
                "campanhas_abertas_total": quantidade_abertas,
                "cliques_total": quantidade_cliques,
                "sessoes_total": sum(numero(i.sessoes_site_app) for i in ids_interacoes),
                "carrinhos_abandonados_total": sum(numero(i.carrinhos_abandonados) for i in ids_interacoes),
                "tickets_sac_total": quantidade_tickets,
                "tickets_resolvidos_total": tickets_resolvidos,
                "taxa_abertura_campanhas": round(quantidade_abertas / quantidade_campanhas, 4) if quantidade_campanhas else 0.0,
                "taxa_clique_campanhas": round(quantidade_cliques / quantidade_campanhas * 100, 4) if quantidade_campanhas else 0.0,
                "taxa_resolucao_sac": round(tickets_resolvidos / quantidade_tickets, 4) if quantidade_tickets else 0.0,
                "campanhas_reativacao_por_campanha": round(sum(numero(i.campanhas_reativacao_recebidas) for i in ids_interacoes) / quantidade_campanhas, 4) if quantidade_campanhas else 0.0,
                "cliques_por_campanha_aberta": round(quantidade_cliques / quantidade_abertas, 4) if quantidade_abertas else 0.0,
                "sessoes_por_pedido": round(sum(numero(i.sessoes_site_app) for i in ids_interacoes) / quantidade_pedidos, 4) if quantidade_pedidos else 0.0,
                "tickets_por_pedido": round(quantidade_tickets / quantidade_pedidos, 4) if quantidade_pedidos else 0.0,
                "carrinhos_por_sessao": round(sum(numero(i.carrinhos_abandonados) for i in ids_interacoes) / sum(numero(i.sessoes_site_app) for i in ids_interacoes), 4) if sum(numero(i.sessoes_site_app) for i in ids_interacoes) else 0.0,
                "sem_interacao": not bool(ids_interacoes),
                "data_referencia": data_referencia,
                "versao_atributos": VERSAO_ATRIBUTOS,
                "gerado_em": agora,
            })

        # A tabela representa o universo atual de resgate. Se os atributos
        # forem regenerados, clusters antigos deixam de ser válidos.
        session.execute(insert(DadosClientes), registros)
        session.commit()
    return len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    parser.add_argument(
        "--data-referencia", type=date.fromisoformat, default=DATA_REFERENCIA_PADRAO,
        help="data limite dos pedidos (padrão: 2026-06-30)",
    )
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        quantidade = criar_dados_clientes(args.banco, args.data_referencia)
    except Exception as erro:
        raise SystemExit(f"Não foi possível criar dados_clientes: {erro}") from erro
    print(f"Tabela 'dados_clientes' atualizada com {quantidade} clientes.")


if __name__ == "__main__":
    main()
