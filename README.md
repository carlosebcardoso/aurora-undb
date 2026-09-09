# Aurora UNDB — importador CSV para SQLite

Ambiente inicial em Python para converter arquivos CSV de uma pasta em tabelas SQLite.

## Configuração

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

## Uso

Coloque os arquivos `.csv` em `dados/` e execute:

```bash
python scripts/import_csv.py
```

Por padrão, o banco será criado como `dados.sqlite3`. Também é possível informar os caminhos:

```bash
python scripts/import_csv.py --pasta ./meus-csvs --banco ./meu-banco.sqlite3
```

Cada CSV vira uma tabela com o mesmo nome do arquivo, usando os modelos ORM fixos em `models/`. Após a migração estrutural, `clientes.id_cliente` e `pedidos.id_pedido` são chaves primárias; `interacoes` e `pedido_itens` usam uma chave técnica `id` autoincrementada. O cabeçalho deve conter as colunas do respectivo model. Campos vazios viram `NULL`, e os tipos são convertidos pelo SQLAlchemy. Depois de carregada, uma tabela existente é ignorada.

A conversão já cria o schema final, separa os itens de pedido, remove duplicidades, aplica as limpezas e cria as chaves relacionais. Para converter novamente os CSVs desde o início:

```bash
python3 scripts/import_csv.py --pasta ./dados --banco ./dados.sqlite3 --reiniciar
```

O resultado cria `pedido_itens`, mantém uma linha por `id_pedido` em `pedidos` e usa `id_cliente` e `id_pedido` como chaves primárias dos respectivos pais.

Para carregar novamente os dados desde o início:

```bash
python3 scripts/import_csv.py --pasta ./consultas --reiniciar
```

## Limpeza dos dados

Depois da importação, execute a limpeza das siglas de estado:

```bash
python3 scripts/limpeza.py --banco ./dados.sqlite3
```

O script converte nomes completos, siglas em minúsculo e valores com acentos para a sigla oficial. Também coloca em maiúsculo e remove acentos dos campos textuais configurados em `scripts/limpeza.py`. Valores desconhecidos de UF são preservados e listados no final.

Ele também corrige `data_pedido` com as datas sentinela `1900-01-01` e `2099-12-31`, usando uma data válida de outro registro com o mesmo `id_pedido`. Quando não existe uma data válida para fazer a substituição, o registro é removido da base.
Valores nulos ou `0` em `pedidos.atraso_entrega_dias` são mantidos como `0`.
Clientes com `optout = true` e seus pedidos, itens e interações relacionados são preservados. A coluna `optout` também é mantida na tabela `clientes`.

## Consultas

Salve seus scripts SQL na pasta `consultas/` e execute um deles pelo fluxo principal:

```bash
python scripts/import_csv.py
python main.py --consulta consultas/minha_consulta.sql
```

O banco é aberto automaticamente pelo `main.py`. Para usar outro arquivo SQLite:

```bash
python main.py --banco ./outro.sqlite3 --consulta consultas/minha_consulta.sql
```

Consultas que retornam dados são exibidas no terminal. Scripts SQL sem resultado, como `CREATE`, `UPDATE` ou `DELETE`, apenas exibem uma mensagem de sucesso.

## Relatório de clientes

Para exibir a quantidade e a porcentagem de clientes por estado, faixa etária e canal de aquisição:

```bash
python3 scripts/relatorio_clientes.py --banco ./dados.sqlite3
```

Para comparar os registros que possuem o mesmo `id_pedido`:

```bash
python3 scripts/comparar_pedidos.py --banco ./dados.sqlite3
```

O script informa quantos grupos de pedidos repetidos possuem todos os campos iguais, quantos possuem divergências e quais campos divergem.

Para contar pedidos com `data_pedido` e registros de `ano_mes` fora do intervalo de 01/07/2023 a 30/06/2026, incluindo a verificação de datas inválidas:

```bash
python3 scripts/pedidos_fora_periodo.py --banco ./dados.sqlite3
```

Para calcular a média de atraso de entrega por UF, desconsiderando pedidos sem atraso:

```bash
python3 scripts/media_atraso_por_uf.py --banco ./dados.sqlite3
```

Para adicionar e atualizar a coluna `inativo` na tabela `clientes`, considerando
os 180 dias anteriores a 30/06/2026:

```bash
python3 scripts/marcar_clientes_inativos.py --banco ./dados.sqlite3
```

Clientes que não fizeram nenhuma compra nos 180 dias anteriores à data de corte
recebem `inativo = 1`. Basta uma compra nesse período para o cliente ficar com
`inativo = 0`; clientes sem compras também são considerados inativos.

Para criar a tabela `analise_clientes` com os dados cadastrais e as métricas de
pedidos:

```bash
python3 scripts/criar_analise_clientes.py --banco ./dados.sqlite3
```

O campo `canal` é preenchido a partir de `clientes.canal_aquisicao`. A média e o
desvio padrão são calculados sobre os intervalos entre pedidos consecutivos;
clientes com menos de dois pedidos ficam com essas métricas como `NULL`. A tabela
também inclui `maior_intervalo`, `menor_intervalo` e `mediana_pedidos`, calculados
sobre os mesmos intervalos.

Para comparar os indicadores dos clientes ativos e inativos:

```bash
python3 scripts/relatorio_ativos_inativos.py --banco ./dados.sqlite3
```

O relatório exibe ticket médio por pedido, média de pedidos por cliente,
intervalos entre pedidos, atraso médio, percentuais de SAC, SAC não resolvido,
pedidos com atraso e cupom, com colunas separadas para ativos, inativos e o
total geral.

Para gerar o relatório detalhado de SAC e comportamento por cliente:

```bash
python3 scripts/relatorio_sac_clientes.py --banco ./dados.sqlite3
```

Ele mostra a distribuição dos motivos de SAC entre ativos e inativos e, por
grupo e no total, a média de SACs por cliente, o percentual médio de pedidos
com cupom, o atraso máximo médio, o atraso médio do último pedido e os dias
médios entre o último SAC e a última compra.

Para calcular a relação temporal entre o último SAC e a última compra:

```bash
python3 scripts/relatorio_relacao_temporal.py --banco ./dados.sqlite3
```

O resultado compara ativos, inativos e total, considerando somente clientes
com último SAC e última compra identificados.

Para distribuir o motivo do último SAC ocorrido após a última compra:

```bash
python3 scripts/relatorio_motivo_ultimo_sac.py --banco ./dados.sqlite3
```

O relatório apresenta quantidade e percentual por motivo para clientes ativos,
inativos e o total. Os percentuais usam como base os clientes cujo último SAC
ocorreu após a última compra.

## Dados para clustering

Para consolidar uma linha tratada por cliente, pronta para o pré-processamento
do clustering, execute:

```bash
python3 scripts/criar_dados_clientes.py --banco ./dados.sqlite3
```

O script cria ou atualiza as tabelas `dados_clientes`, `clusters_clientes`,
`resultados_cluster` e `desvios_cluster`.
`dados_clientes` contém somente clientes atualmente marcados como inativos que
possuem pelo menos dois pedidos válidos até a data de referência. A tabela combina
cadastro, pedidos, itens e interações. A data de
referência padrão é `2026-06-30` e pode ser alterada com `--data-referencia
YYYY-MM-DD`.

A condição de inatividade é aplicada usando `clientes.inativo`; por isso,
`dados_clientes` não repete essa coluna constante.

Os valores numéricos de atividade ausente são tratados como zero. Como todos
os clientes possuem pelo menos dois pedidos, as métricas de intervalo sempre
têm histórico e não precisam de variáveis indicadoras de existência. O campo
`sem_interacao` preserva a ausência de interações. O valor de cada item é calculado como
`quantidade * valor_unitario - valor_desconto`; `valor_desconto` é considerado o
desconto total do item.

`clusters_clientes` e `resultados_cluster` são criadas vazias e receberão os
resultados do algoritmo de cluster em uma etapa posterior. Ao regenerar
`dados_clientes`, os clusters
anteriores são removidos porque podem estar associados a outro conjunto de
clientes inativos.

Para executar o clustering dos clientes inativos:

```bash
python3 scripts/rodar_cluster_clientes.py --banco ./dados.sqlite3
```

Por padrão, o script testa `k` de 3 a 6, escolhe o melhor silhouette score
entre as soluções sem clusters menores que 5% da base e grava uma linha por
cliente em `clusters_clientes`, uma linha por grupo em `resultados_cluster`,
contendo a quantidade de clientes e as médias, e uma linha por atributo e
grupo em `desvios_cluster`, contendo os desvios padrão. O modelo usa dimensões
interpretáveis de recência, frequência, valor, engajamento, sensibilidade a
desconto e fricção logística. Valor e frequência recebem transformação
logarítmica antes da padronização para reduzir a influência de outliers.
Para fixar a quantidade de
grupos, use `--k`, por exemplo `--k 4`. O conjunto de variáveis utilizado, o
score, a versão dos atributos e a data de referência ficam registrados na
tabela.

Para testar combinações de atributos e valores de `k` pelo silhouette score:

```bash
python3 scripts/buscar_combinacao_cluster.py --banco ./dados.sqlite3 --saida avaliacoes_cluster.csv
```

Por padrão, são testadas todas as combinações de 2 a 4 atributos e `k` de 2 a
8, rejeitando soluções com algum cluster menor que 5% da base. O limite de
atributos e o percentual mínimo podem ser alterados com
`--tamanho-maximo` e `--percentual-minimo-cluster`. O resultado é salvo em CSV,
ordenado pelo score, e a melhor combinação é exibida no terminal.

Para visualizar os clusters em uma interface web local:

```bash
python3 scripts/visualizar_clusters.py --banco ./dados.sqlite3
```

Depois, acesse `http://127.0.0.1:8000`. A página apresenta cartões de resumo,
perfis comparativos por cluster, filtro por grupo, busca textual e uma tabela
com as principais métricas de cada cliente. Execute novamente o clustering e
atualize a página para visualizar uma nova versão dos resultados.
