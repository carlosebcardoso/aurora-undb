#!/usr/bin/env python3
"""Executa K-Means nos clientes inativos e grava seus clusters no SQLite."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from statistics import pstdev

from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import ClustersClientes, DadosClientes, DesviosCluster, ResultadosCluster


VARIAVEIS = (
    # Dimensões comportamentais que podem orientar uma ação de resgate.
    "dias_desde_ultimo_pedido",         # recência / urgência
    "quantidade_pedidos",               # frequência / vínculo
    "valor_total_compras",              # valor histórico
    "taxa_abertura_campanhas",          # interesse em comunicação
    "taxa_clique_campanhas",            # intenção mais forte
    "percentual_pedidos_com_desconto",  # sensibilidade a preço
    "percentual_pedidos_com_atraso",    # fricção logística
    # sem_interacao fica como marcador de interpretação, não como eixo do
    # clustering: seus poucos casos formavam um microcluster artificial.
)
NOME_VARIAVEIS = ",".join(VARIAVEIS)
VERSAO_CLUSTER = "v2-perfis-acionaveis"
VARIAVEIS_RESUMO = (
    "dias_desde_cadastro", "quantidade_pedidos", "dias_desde_ultimo_pedido",
    "intervalo_medio_pedidos", "intervalo_mediano_pedidos",
    "intervalo_minimo_pedidos", "intervalo_maximo_pedidos",
    "desvio_intervalo_pedidos", "quantidade_itens",
    "quantidade_skus_distintos", "quantidade_categorias_distintas",
    "valor_total_compras", "ticket_medio", "ticket_mediano",
    "desconto_total", "percentual_pedidos_com_desconto", "percentual_pedidos_com_cupom",
    "itens_por_pedido", "margem_media",
    "quantidade_pedidos_com_cupom", "prazo_medio_entrega",
    "atraso_medio_entrega", "maior_atraso_entrega", "pedidos_com_atraso",
    "percentual_pedidos_com_atraso", "meses_com_interacao",
    "campanhas_enviadas_total", "campanhas_reativacao_total",
    "campanhas_abertas_total", "cliques_total", "sessoes_total",
    "carrinhos_abandonados_total", "tickets_sac_total",
    "tickets_resolvidos_total", "taxa_abertura_campanhas",
    "taxa_clique_campanhas", "taxa_resolucao_sac",
    "campanhas_reativacao_por_campanha", "cliques_por_campanha_aberta",
    "sessoes_por_pedido", "tickets_por_pedido", "carrinhos_por_sessao",
    "sem_interacao",
)


def preparar_matriz(registros):
    """Reduz o efeito de outliers antes de padronizar as dimensões."""
    valores = np.array(
        [[float(getattr(registro, variavel)) for variavel in VARIAVEIS] for registro in registros],
        dtype=float,
    )
    for variavel in ("quantidade_pedidos", "valor_total_compras"):
        indice = VARIAVEIS.index(variavel)
        valores[:, indice] = np.log1p(np.maximum(valores[:, indice], 0))
    return StandardScaler().fit_transform(valores)


def executar_cluster(
    banco: Path,
    quantidade_clusters: int | None,
    k_minimo: int,
    k_maximo: int,
    random_state: int,
) -> tuple[int, float, int]:
    engine = create_engine(f"sqlite:///{banco}")
    ResultadosCluster.__table__.drop(engine, checkfirst=True)
    ResultadosCluster.__table__.create(engine)
    DesviosCluster.__table__.drop(engine, checkfirst=True)
    DesviosCluster.__table__.create(engine)
    with Session(engine) as session:
        registros = list(session.scalars(select(DadosClientes).order_by(DadosClientes.id_cliente)))
        if not registros:
            raise RuntimeError(
                "dados_clientes não possui registros. Execute primeiro "
                "scripts/criar_dados_clientes.py."
            )
        if len(registros) < 2:
            raise RuntimeError("São necessários pelo menos dois clientes para clusterizar.")

        matriz_padronizada = preparar_matriz(registros)

        if quantidade_clusters is not None:
            candidatos = [quantidade_clusters]
        else:
            candidatos = list(range(max(3, k_minimo), min(k_maximo, 6, len(registros) - 1) + 1))
        if not candidatos:
            raise ValueError("Intervalo de k inválido para a quantidade de clientes disponível.")
        if any(k < 2 or k >= len(registros) for k in candidatos):
            raise ValueError("Cada valor de k deve ser maior ou igual a 2 e menor que o total de clientes.")

        avaliados = []
        for k in candidatos:
            modelo = KMeans(n_clusters=k, n_init=20, random_state=random_state)
            rotulos = modelo.fit_predict(matriz_padronizada)
            tamanhos = np.bincount(rotulos, minlength=k)
            if min(tamanhos) < len(registros) * 0.05:
                continue
            score = silhouette_score(matriz_padronizada, rotulos)
            avaliados.append((score, k, modelo, rotulos))
        if not avaliados:
            raise ValueError("Nenhum k gerou clusters com pelo menos 5% dos clientes.")
        score, k_escolhido, modelo, rotulos = max(avaliados, key=lambda item: item[0])

        agora = datetime.now().replace(microsecond=0)
        data_referencia = registros[0].data_referencia
        versao = registros[0].versao_atributos
        session.execute(ClustersClientes.__table__.delete())
        session.execute(insert(ClustersClientes), [
            {
                "id_cliente": registro.id_cliente,
                "cluster": int(rotulo),
                "algoritmo": "k-means",
                "quantidade_clusters": k_escolhido,
                "data_referencia": data_referencia,
                "data_geracao": agora,
                "versao_atributos": VERSAO_CLUSTER,
                "silhouette_score": round(float(score), 6),
                "conjunto_variaveis": NOME_VARIAVEIS,
            }
            for registro, rotulo in zip(registros, rotulos)
        ])
        resumos = []
        for cluster in range(k_escolhido):
            grupo = [
                registro for registro, rotulo in zip(registros, rotulos)
                if int(rotulo) == cluster
            ]
            resumo = {
                "cluster": cluster,
                "quantidade_clientes": len(grupo),
                "quantidade_clusters": k_escolhido,
                "data_referencia": data_referencia,
                "data_geracao": agora,
                "versao_atributos": VERSAO_CLUSTER,
                "silhouette_score": round(float(score), 6),
            }
            resumo.update({
                variavel: round(
                    sum(float(getattr(registro, variavel)) for registro in grupo) / len(grupo),
                    4,
                )
                for variavel in VARIAVEIS_RESUMO
            })
            resumos.append(resumo)
        session.execute(insert(ResultadosCluster), resumos)
        desvios = []
        for cluster in range(k_escolhido):
            grupo = [
                registro for registro, rotulo in zip(registros, rotulos)
                if int(rotulo) == cluster
            ]
            desvios.extend({
                "cluster": cluster,
                "atributo": variavel,
                "desvio_padrao": round(pstdev(float(getattr(registro, variavel)) for registro in grupo), 4),
                "quantidade_clusters": k_escolhido,
                "data_referencia": data_referencia,
                "data_geracao": agora,
                "versao_atributos": VERSAO_CLUSTER,
            } for variavel in VARIAVEIS_RESUMO)
        session.execute(insert(DesviosCluster), desvios)
        session.commit()
        return k_escolhido, float(score), len(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    parser.add_argument("--k", type=int, help="quantidade fixa de clusters")
    parser.add_argument("--k-min", type=int, default=3)
    parser.add_argument("--k-max", type=int, default=6)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        k, score, quantidade = executar_cluster(
            args.banco, args.k, args.k_min, args.k_max, args.random_state
        )
    except Exception as erro:
        raise SystemExit(f"Não foi possível executar o cluster: {erro}") from erro
    print(f"Cluster concluído para {quantidade} clientes inativos.")
    print(f"k escolhido: {k} | silhouette score: {score:.4f}")


if __name__ == "__main__":
    main()
