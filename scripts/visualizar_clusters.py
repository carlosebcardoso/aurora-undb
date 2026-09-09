#!/usr/bin/env python3
"""Abre uma visualização web local dos clusters de clientes inativos."""

from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clusters de clientes inativos</title>
  <style>
    :root { --bg:#f4f7fb; --card:#fff; --ink:#152238; --muted:#65748b; --line:#dce4ef; --accent:#276ef1; --accent-soft:#eaf1ff; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }
    .shell { max-width:1500px; margin:auto; padding:30px 24px 50px; }
    header { display:flex; justify-content:space-between; align-items:flex-end; gap:20px; margin-bottom:24px; }
    h1 { margin:0 0 5px; font-size:28px; letter-spacing:-.03em; }
    h2 { margin:0 0 16px; font-size:18px; }
    .subtitle, .muted { color:var(--muted); }
    .badge { background:var(--accent-soft); color:var(--accent); border-radius:999px; padding:7px 12px; font-weight:700; white-space:nowrap; }
    .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:24px; }
    .card, .panel { background:var(--card); border:1px solid var(--line); border-radius:14px; box-shadow:0 5px 18px #172b4d0b; }
    .card { padding:18px; }
    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
    .value { display:block; margin-top:8px; font-size:25px; font-weight:800; }
    .panel { padding:20px; margin-bottom:20px; }
    .profiles { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    .profile { border:1px solid var(--line); border-radius:12px; padding:16px; background:#fbfcff; }
    .profile-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
    .cluster-name { font-weight:800; font-size:16px; }
    .cluster-count { color:var(--muted); font-size:12px; }
    .profile-motivation { color:var(--muted); font-size:12px; line-height:1.4; margin:-4px 0 12px; }
    .profile-motivation strong { color:var(--ink); }
    .metric { margin-top:10px; }
    .metric-row { display:flex; justify-content:space-between; gap:8px; color:var(--muted); font-size:12px; }
    .metric-row strong { color:var(--ink); }
    .bar { height:7px; background:#e7edf6; border-radius:99px; overflow:hidden; margin-top:5px; }
    .bar i { display:block; height:100%; background:var(--accent); border-radius:inherit; }
    .focus { margin-top:16px; padding-top:14px; border-top:1px solid var(--line); }
    .focus-title { color:var(--accent); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; margin-bottom:8px; }
    .focus-heading { display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px; }
    .focus-heading .focus-title { margin-bottom:0; }
    .toggle-attributes { border:0; background:var(--accent-soft); color:var(--accent); border-radius:7px; padding:5px 8px; font-family:inherit; font-size:11px; font-weight:700; cursor:pointer; white-space:nowrap; }
    .toggle-attributes:hover { background:#dce8ff; }
    .focus-grid { display:grid; grid-template-columns:1fr; gap:9px; }
    .focus-item { font-size:12px; }
    .focus-item-head { display:flex; justify-content:space-between; gap:8px; }
    .focus-item span { color:var(--muted); overflow:hidden; text-overflow:ellipsis; }
    .focus-item strong { white-space:nowrap; }
    .std { color:var(--muted); font-size:11px; margin-top:3px; }
    .focus-bar { height:5px; background:#e7edf6; border-radius:99px; overflow:hidden; margin-top:4px; }
    .focus-bar i { display:block; height:100%; background:#6f9cf7; border-radius:inherit; }
    .std-bar { height:5px; background:#edf0f5; border-radius:99px; overflow:hidden; margin-top:4px; }
    .std-bar i { display:block; height:100%; background:#aebbd0; border-radius:inherit; }
    .other-metrics.is-collapsed .metric:nth-child(n+6) { display:none; }
    .toolbar { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:16px; }
    input, select { border:1px solid var(--line); background:white; color:var(--ink); border-radius:9px; padding:10px 12px; font:inherit; }
    input { min-width:250px; flex:1; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:10px; }
    table { width:100%; border-collapse:collapse; min-width:1050px; background:white; }
    th, td { padding:13px 15px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
    th { position:sticky; top:0; background:#f7f9fc; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(11), td:nth-child(11) { text-align:left; }
    tr:last-child td { border-bottom:0; }
    .cluster-pill { display:inline-block; background:var(--accent-soft); color:var(--accent); border-radius:999px; padding:3px 9px; font-weight:700; }
    .empty { padding:30px; text-align:center; color:var(--muted); }
    footer { color:var(--muted); font-size:12px; margin-top:12px; }
    @media (max-width:1100px) { .profiles { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:700px) { .shell { padding:20px 14px 35px; } header { display:block; } .badge { display:inline-block; margin-top:14px; } h1 { font-size:24px; } .profiles { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main class="shell">
  <header>
    <div><h1>Clientes inativos</h1><div class="subtitle">Perfis para orientar ações de resgate</div></div>
    <div id="model-badge" class="badge">Carregando...</div>
  </header>
  <section id="cards" class="cards"></section>
  <section class="panel"><h2>Perfil dos clusters</h2><div id="profiles" class="profiles"></div></section>
  <section class="panel">
    <h2>Clientes por cluster</h2>
    <div class="toolbar">
      <select id="cluster-filter"><option value="">Todos os clusters</option></select>
      <input id="search" placeholder="Buscar por ID, canal, tier ou faixa etária...">
    </div>
    <div id="table-container" class="table-wrap"></div>
    <footer id="row-count"></footer>
  </section>
</main>
<script>
const DATA = __DATA__;
const money = v => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v || 0);
const number = (v,d=2) => Number(v || 0).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const integer = v => Number(v || 0).toLocaleString('pt-BR');
const pct = v => `${number((v || 0) * 100, 1)}%`;
const maxFor = key => Math.max(...DATA.resumos.map(x => Number(x[key]) || 0), 1);
const featureLabels = {
  dias_desde_cadastro:'Dias desde cadastro', quantidade_pedidos:'Pedidos', dias_desde_ultimo_pedido:'Recência',
  intervalo_medio_pedidos:'Intervalo médio', intervalo_mediano_pedidos:'Intervalo mediano',
  intervalo_minimo_pedidos:'Menor intervalo', intervalo_maximo_pedidos:'Maior intervalo',
  desvio_intervalo_pedidos:'Desvio do intervalo', quantidade_itens:'Itens',
  quantidade_skus_distintos:'SKUs distintos', quantidade_categorias_distintas:'Categorias distintas',
  valor_total_compras:'Valor total', ticket_medio:'Ticket médio', ticket_mediano:'Ticket mediano',
  desconto_total:'Desconto total', percentual_pedidos_com_desconto:'Pedidos com desconto',
  percentual_pedidos_com_cupom:'Pedidos com cupom', itens_por_pedido:'Itens por pedido', margem_media:'Margem média',
  quantidade_pedidos_com_cupom:'Pedidos com cupom (quantidade)', prazo_medio_entrega:'Prazo médio',
  atraso_medio_entrega:'Atraso médio', maior_atraso_entrega:'Maior atraso', pedidos_com_atraso:'Pedidos com atraso',
  percentual_pedidos_com_atraso:'Pedidos com atraso', meses_com_interacao:'Meses com interação',
  campanhas_enviadas_total:'Campanhas enviadas', campanhas_reativacao_total:'Campanhas de reativação',
  campanhas_abertas_total:'Campanhas abertas', cliques_total:'Cliques', sessoes_total:'Sessões',
  carrinhos_abandonados_total:'Carrinhos abandonados', tickets_sac_total:'Tickets SAC',
  tickets_resolvidos_total:'Tickets resolvidos', taxa_abertura_campanhas:'Taxa de abertura',
  taxa_clique_campanhas:'Taxa de clique', taxa_resolucao_sac:'Taxa de resolução SAC', sem_interacao:'Sem interação',
  campanhas_reativacao_por_campanha:'Reativação por campanha', cliques_por_campanha_aberta:'Cliques por abertura',
  sessoes_por_pedido:'Sessões por pedido', tickets_por_pedido:'Tickets por pedido', carrinhos_por_sessao:'Carrinhos por sessão'
};
const allMetricKeys = Object.keys(featureLabels);
const PREVIEW_OTHER_LIMIT = 5;
const importantOtherKeys = [
  'dias_desde_ultimo_pedido', 'quantidade_pedidos', 'valor_total_compras',
  'ticket_medio', 'atraso_medio_entrega', 'taxa_abertura_campanhas',
  'percentual_pedidos_com_desconto', 'tickets_sac_total'
];
const formatFeature = (key, value) => {
  if (key === 'taxa_clique_campanhas') return `${number(value, 1)}%`;
  if (key.includes('percentual') || key.includes('taxa_') || key === 'sem_interacao') return pct(value);
  if (key.includes('valor') || key.includes('ticket') || key.includes('desconto')) return money(value);
  if (key.includes('dias') || key.includes('intervalo') || key.includes('atraso')) return `${number(value, 1)} d`;
  return number(value, 1);
};
const stdFor = (cluster, key) => Number((DATA.desvios[cluster] || {})[key] || 0);
const maxStdFor = key => Math.max(...DATA.resumos.map(r => stdFor(r.cluster, key)), 1);
const renderMetric = (r, key, color) => `<div class="metric"><div class="metric-row"><span>${featureLabels[key] || key}</span><strong>${formatFeature(key, r[key])}</strong></div><div class="bar"><i style="background:${color};width:${Math.min(100,(Number(r[key]) || 0) / maxFor(key) * 100)}%"></i></div><div class="std">Desvio padrão: ${formatFeature(key, stdFor(r.cluster, key))}</div><div class="std-bar"><i style="width:${Math.min(100,stdFor(r.cluster, key) / maxStdFor(key) * 100)}%"></i></div></div>`;
const maxSummary = key => Math.max(...DATA.resumos.map(r => Number(r[key]) || 0), 1);
const profileInterpretation = r => {
  const highValue = (Number(r.valor_total_compras) || 0) >= maxSummary('valor_total_compras') * .75 || (Number(r.quantidade_pedidos) || 0) >= maxSummary('quantidade_pedidos') * .75;
  const engaged = (Number(r.taxa_abertura_campanhas) || 0) >= maxSummary('taxa_abertura_campanhas') * .75 && (Number(r.taxa_clique_campanhas) || 0) >= maxSummary('taxa_clique_campanhas') * .75;
  const lapsed = (Number(r.dias_desde_ultimo_pedido) || 0) >= maxSummary('dias_desde_ultimo_pedido') * .75;
  const friction = (Number(r.percentual_pedidos_com_atraso) || 0) >= maxSummary('percentual_pedidos_com_atraso') * .75;
  const discount = (Number(r.percentual_pedidos_com_desconto) || 0) >= maxSummary('percentual_pedidos_com_desconto') * .75;
  if (engaged && highValue) return ['Alto valor e engajamento', 'reativar com novidades, benefícios e recomendação personalizada.'];
  if (lapsed && friction) return ['Inatividade associada à fricção', 'recuperar a confiança com suporte e solução para a entrega antes de ofertar.'];
  if (highValue && discount) return ['Alto valor sensível a preço', 'testar benefício financeiro controlado, cashback ou condição exclusiva.'];
  if (lapsed) return ['Baixo vínculo e longo tempo inativo', 'começar com uma oferta simples e explicar claramente o benefício de voltar.'];
  return ['Relacionamento intermediário', discount ? 'usar incentivo de preço com limite e medir a resposta.' : 'testar comunicação personalizada e observar o próximo sinal de interesse.'];
};

document.getElementById('model-badge').textContent = `${DATA.model.k} clusters · silhouette ${number(DATA.model.score, 3)}`;
document.getElementById('cards').innerHTML = [
  ['Clientes analisados', integer(DATA.total)],
  ['Clusters gerados', integer(DATA.model.k)],
  ['Silhouette score', number(DATA.model.score, 3)],
  ['Data de referência', DATA.model.data_referencia]
].map(([label,value]) => `<div class="card"><span class="label">${label}</span><span class="value">${value}</span></div>`).join('');

document.getElementById('profiles').innerHTML = DATA.resumos.map(r => {
  const selectedKeys = DATA.model.features;
  const availableOtherKeys = allMetricKeys.filter(key => !selectedKeys.includes(key) && r[key] !== undefined);
  const otherKeys = [...importantOtherKeys.filter(key => availableOtherKeys.includes(key)), ...availableOtherKeys.filter(key => !importantOtherKeys.includes(key))];
  const selected = selectedKeys.map(key => renderMetric(r, key, 'var(--accent)')).join('');
  const others = otherKeys.map(key => renderMetric(r, key, '#8ca9d9')).join('');
  const hasMore = otherKeys.length > PREVIEW_OTHER_LIMIT;
  const [motivation, action] = profileInterpretation(r);
  return `<article class="profile"><div class="profile-head"><span class="cluster-name">Cluster ${r.cluster}</span><span class="cluster-count">${integer(r.quantidade_clientes)} clientes</span></div>` +
    `<div class="profile-motivation"><strong>${motivation}</strong><br>Ação sugerida: ${action}</div>` +
    `<div class="focus"><div class="focus-title">Atributos usados no cluster</div>${selected}</div>` +
    `<div class="focus"><div class="focus-heading"><div class="focus-title">Demais atributos</div>${hasMore ? `<button class="toggle-attributes" type="button" aria-expanded="false">Mostrar todos (${otherKeys.length})</button>` : ''}</div><div class="other-metrics${hasMore ? ' is-collapsed' : ''}">${others}</div></div></article>`;
}).join('');

document.querySelectorAll('.toggle-attributes').forEach(button => button.addEventListener('click', () => {
  const metrics = button.closest('.focus').querySelector('.other-metrics');
  const expanded = !metrics.classList.toggle('is-collapsed');
  button.setAttribute('aria-expanded', String(expanded));
  button.textContent = expanded ? 'Mostrar menos' : `Mostrar todos (${metrics.children.length})`;
}));

const filter = document.getElementById('cluster-filter');
DATA.resumos.forEach(r => filter.insertAdjacentHTML('beforeend', `<option value="${r.cluster}">Cluster ${r.cluster}</option>`));
const search = document.getElementById('search');
function render() {
  const term = search.value.toLowerCase().trim(), selected = filter.value;
  const rows = DATA.clientes.filter(r => (!selected || String(r.cluster) === selected) && (!term || Object.values(r).join(' ').toLowerCase().includes(term)));
  const head = ['Cliente','Cluster','Recência','Pedidos','Valor total','Ticket médio','Intervalo médio','Desconto','Atraso','Tickets SAC','Canal','Tier'];
  const body = rows.map(r => `<tr><td>${r.id_cliente}</td><td><span class="cluster-pill">${r.cluster}</span></td><td>${integer(r.dias_desde_ultimo_pedido)} dias</td><td>${integer(r.quantidade_pedidos)}</td><td>${money(r.valor_total_compras)}</td><td>${money(r.ticket_medio)}</td><td>${number(r.intervalo_medio_pedidos,1)} dias</td><td>${pct(r.percentual_pedidos_com_desconto)}</td><td>${number(r.atraso_medio_entrega,1)} dias</td><td>${integer(r.tickets_sac_total)}</td><td>${r.canal_aquisicao}</td><td>${r.tier_clube}</td></tr>`).join('');
  document.getElementById('table-container').innerHTML = rows.length ? `<table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>` : '<div class="empty">Nenhum cliente encontrado.</div>';
  document.getElementById('row-count').textContent = `${integer(rows.length)} cliente(s) exibido(s)`;
}
filter.addEventListener('change', render); search.addEventListener('input', render); render();
</script>
</body>
</html>"""


def carregar_dados(banco: Path) -> dict:
    with sqlite3.connect(banco) as conexao:
        conexao.row_factory = sqlite3.Row
        modelo = conexao.execute(
            "SELECT quantidade_clusters, silhouette_score, data_referencia, conjunto_variaveis "
            "FROM clusters_clientes LIMIT 1"
        ).fetchone()
        if modelo is None:
            raise RuntimeError("clusters_clientes está vazia. Execute o clustering primeiro.")
        resumos = [dict(linha) for linha in conexao.execute(
            "SELECT * FROM resultados_cluster ORDER BY cluster"
        )]
        desvios = {}
        for linha in conexao.execute("SELECT cluster, atributo, desvio_padrao FROM desvios_cluster"):
            desvios.setdefault(str(linha["cluster"]), {})[linha["atributo"]] = linha["desvio_padrao"]
        clientes = [dict(linha) for linha in conexao.execute("""
            SELECT c.id_cliente, c.cluster, d.dias_desde_ultimo_pedido,
                   d.quantidade_pedidos, d.valor_total_compras, d.ticket_medio,
                   d.intervalo_medio_pedidos, d.percentual_pedidos_com_desconto,
                   d.atraso_medio_entrega, d.tickets_sac_total,
                   d.canal_aquisicao, d.tier_clube
            FROM clusters_clientes c
            JOIN dados_clientes d ON d.id_cliente = c.id_cliente
            ORDER BY c.cluster, d.valor_total_compras DESC
        """)]
    return {
        "total": len(clientes),
        "model": {"k": modelo["quantidade_clusters"], "score": modelo["silhouette_score"], "data_referencia": modelo["data_referencia"], "features": modelo["conjunto_variaveis"].split(",")},
        "resumos": resumos,
        "desvios": desvios,
        "clientes": clientes,
    }


class Handler(BaseHTTPRequestHandler):
    banco: Path

    def do_GET(self) -> None:  # noqa: N802
        try:
            dados = carregar_dados(self.banco)
            conteudo = HTML.replace("__DATA__", json.dumps(dados, ensure_ascii=False).replace("<", "\\u003c"))
            payload = conteudo.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (sqlite3.Error, RuntimeError) as erro:
            payload = f"Erro: {erro}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, formato: str, *args) -> None:
        print(f"[{self.log_date_time_string}] {formato % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, default=Path("dados.sqlite3"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not args.banco.is_file():
        raise SystemExit(f"Banco não encontrado: {args.banco}")
    try:
        carregar_dados(args.banco)
    except (sqlite3.Error, RuntimeError) as erro:
        raise SystemExit(f"Não foi possível carregar os clusters: {erro}") from erro
    Handler.banco = args.banco
    servidor = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Visualização disponível em http://{args.host}:{args.port}")
    print("Pressione Ctrl+C para encerrar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
