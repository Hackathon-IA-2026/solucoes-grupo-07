# CurtaMap

> O nome do produto ainda não é definitivo.

Protótipo para antecipar cortes de geração eólica e solar, explicar a causa provável e recomendar como reaproveitar essa energia. O foco inicial é o gerador, com previsões por usina em intervalos de 30 minutos para as próximas 24 horas.

## Demo

- **Link da demo:** a definir

## Estado atual

O repositório contém a base técnica inicial. Ainda não há dataset versionado nem modelo treinado; qualquer número mostrado no app nesta fase é identificado como demonstrativo.

As decisões e perguntas em aberto estão em [docs/architecture.md](docs/architecture.md). O caminho de implementação está em [docs/roadmap.md](docs/roadmap.md).

## Stack

- Python 3.12 e `uv`
- Polars, DuckDB e Parquet para processamento
- scikit-learn e modelos tabulares candidatos para experimentação
- Streamlit como protótipo atual; React/Vite + FastAPI em avaliação para a interface final
- AWS com infraestrutura como código para build, execução, dados, modelos e observabilidade
- Bedrock ou NVIDIA NIM como camada opcional de explicação em linguagem natural

## Pré-requisitos

- Git
- [`uv`](https://docs.astral.sh/uv/) 0.12 ou superior
- Acesso à internet para instalar dependências e baixar as bases
- Espaço em disco compatível com os Parquet escolhidos
- Python 3.12, instalado automaticamente pelo `uv` quando necessário

Docker e AWS CLI não são necessários para o desenvolvimento local inicial. Eles serão documentados quando a infraestrutura AWS for implementada.

## Como executar

```bash
uv sync --dev
cp .env.example .env
uv run streamlit run src/curtamap/app.py
```

As integrações opcionais podem ser instaladas com `uv sync --extra data --extra llm --extra aws --dev`.

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

## Entrega alternativa: quando, causa histórica e decisão em reais

A branch `codex/alertas-impacto-negocio` traz uma demonstração histórica focada em
alertas e avaliação de horários de manutenção flexível, sem previsão de volume.
A causa é contexto histórico observado, não saída do modelo de ocorrência.

```bash
uv run streamlit run src/curtamap/alertas_app.py
```

Veja os [resultados, perdas e recomendação do pivô](docs/reports/alertas/README.md) e o
[passo a passo de reprodução](docs/reports/alertas/COMO-RODAR.md). O cenário solar teve
diferença média favorável em agosto; a eólica perdeu para a referência de menor geração
histórica. Valores em reais são contrafactuais sobre dados ONS/CCEE, não economia realizada.
