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

Não há dependências externas para instalar. O SQLite já vem incluído no Python.

## Uso

Coloque os arquivos `.csv` em `dados/` e execute:

```bash
python scripts/import_csv.py
```

Por padrão, o banco será criado como `dados.sqlite3`. Também é possível informar os caminhos:

```bash
python scripts/import_csv.py --pasta ./meus-csvs --banco ./meu-banco.sqlite3
```

Cada CSV vira uma tabela com o mesmo nome do arquivo, sem a extensão. A primeira linha deve conter os nomes das colunas. Arquivos sem dados são ignorados. Se a tabela já existir, o CSV é ignorado e não altera os dados existentes.

