# CurtaMap

> O nome do produto ainda não é definitivo.

Protótipo para antecipar cortes de geração eólica e solar, explicar a causa provável e recomendar como reaproveitar essa energia. O foco inicial é o gerador, com previsões por usina em intervalos de 30 minutos para as próximas 24 horas.

## Demo

- **Link da demo:** a definir

## Estado atual

A interface em Streamlit tem três telas: **Operação D+1** (usinas em risco nas próximas 24 h,
perfil das 48 janelas e ações), **Visão tática** (perdas observadas) e **Metodologia e
limites**. Ela usa o modelo diário em `models/previsao/`, quando existe, ou o preditor
provisório (baseline), sempre com um selo que diz qual dos dois. As recomendações ainda são
um exemplo simulado e rotulado até a Etapa 3 chegar ao `main`.

As decisões e perguntas em aberto estão em [docs/architecture.md](docs/architecture.md). O caminho de implementação está em [docs/roadmap.md](docs/roadmap.md).

## Stack

- Python 3.12 e `uv`
- Polars, DuckDB e Parquet para processamento
- scikit-learn e modelos tabulares candidatos para experimentação
- Streamlit para a interface (telas em `src/curtamap/ui/`, cálculos testados em `src/curtamap/painel/`)
- AWS com infraestrutura como código para build, execução, dados, modelos e observabilidade
- Bedrock ou NVIDIA NIM como camada opcional de explicação em linguagem natural

## Pré-requisitos

- Git
- [`uv`](https://docs.astral.sh/uv/) 0.12 ou superior
- Acesso à internet para instalar dependências e baixar as bases
- Espaço em disco compatível com os Parquet escolhidos
- Python 3.12, instalado automaticamente pelo `uv` quando necessário

Docker, Node/pnpm e AWS CLI só são necessários para o deploy; veja [docs/deploy.md](docs/deploy.md).

## Como executar

```bash
uv sync --extra data --dev
cp .env.example .env
uv run python -m curtamap.download_data     # Parquet do ONS em data/raw/
uv run streamlit run src/curtamap/app.py
```

Sem os Parquet, a interface mostra como obtê-los em vez de números. O modelo diário é
opcional (treino em [docs/deploy.md](docs/deploy.md), seção 1).

As integrações opcionais podem ser instaladas com `uv sync --extra data --extra llm --extra aws --extra infra --dev`.

Validações:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Dados

As bases oficiais podem ser listadas e baixadas automaticamente da pasta pública indicada no Caderno:

```bash
uv sync --extra data --dev
uv run python -m curtamap.download_data --list
uv run python -m curtamap.download_data
```

Por padrão, o script baixa somente os cinco Parquet do ONS para `data/raw/`. Use `--include-tutorials` para incluir também o material ERA5. Downloads existentes são preservados; use `--force` apenas quando quiser substituí-los.

O diretório é ignorado pelo Git. Consulte [data/README.md](data/README.md) para as convenções de dados.

## Licença

MIT. Consulte [LICENSE](LICENSE).
