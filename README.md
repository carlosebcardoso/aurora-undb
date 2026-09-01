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
Valores `0` em `pedidos.atraso_entrega_dias` são convertidos para `NULL`.
Clientes com `optout = true` e seus pedidos, itens e interações relacionados são removidos; depois a coluna `optout` não faz parte da tabela `clientes`.

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
