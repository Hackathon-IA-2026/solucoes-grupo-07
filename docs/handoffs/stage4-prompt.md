# Prompt autossuficiente para a Etapa 4 (interface) e a preparação da Etapa 5 (AWS)

Você vai construir a interface do CurtaMap em **Streamlit** e, na quinta-feira (24/09), preparar
localmente o deploy da Etapa 5. O usuário principal é o **gerador eólico/solar**. O dashboard
abre com a decisão que ele precisa tomar, não com a acurácia do modelo: usinas em risco,
janela, MWh, causa, confiança e ação sugerida.

## Antes de começar

Leia integralmente: `AGENTS.md`, `docs/parallel-plan.md`, `docs/architecture.md`,
`docs/roadmap.md` (seções 4 e 5), `docs/aws-environment.md`, `docs/pitch-notes.md`,
`src/curtamap/contracts.py`, `src/curtamap/forecasting.py` e o `src/curtamap/app.py` atual.
Leia também as últimas entradas de `docs/implementation-journal.md`.

Trabalhe na branch `etapa-4-interface`, criada a partir do `origin/main` atualizado. Faça commits
atômicos em português (Conventional Commits) e push da branch. Não faça merge no `main`: a
integração é por Pull Request revisado pelo responsável.

Para ter dados reais: `uv sync --extra data --dev` e `uv run python -m curtamap.download_data`.

## Contratos que a interface consome

- **Previsão:** `load_history(settings.data_dir, inicio, fim)` e
  `SameSlotRecentBaseline().predict(history, t0, nightly_cutoff(t0))` devolvem um DataFrame
  Polars no formato `FORECAST_SCHEMA`, com 48 janelas por usina. Carregar 28 dias leva menos
  de 1 s. O preditor definitivo da Etapa 2 vai substituir este depois, com o mesmo formato. A
  interface não pode depender de qual preditor gerou a previsão, nem importar
  `curtamap.experimental`.
- **Atributos das usinas:** `known_entities(history, corte)` devolve nome, UF e subsistema.
- **Recomendação:** `RECOMMENDATION_SCHEMA`. O módulo que gera recomendações está sendo feito em
  paralelo por outro desenvolvedor (branch `etapa-3-recomendacao`). Até ele chegar ao `main`,
  construa o painel de ações sobre uma fixture pequena que passe por
  `validate_recommendations`, com `tipo_saida = "simulado"` e um aviso visível na tela de que
  é um exemplo. Quando o módulo real chegar, só a origem dos dados muda.

Se precisar de uma coluna nova no contrato, pare e proponha ao responsável um PR pequeno e
separado em `contracts.py`. Não implemente regras de recomendação nem cálculos de impacto: são
da Etapa 3.

## Entregas da Etapa 4 (terça a quinta)

1. **Estrutura multipágina** com `st.navigation`. O `app.py` só configura a página e registra
   as telas. Cada tela fica em um módulo próprio (por exemplo `src/curtamap/ui/`).
   **A interface só desenha.** Qualquer cálculo reaproveitável vai para funções testadas fora da
   UI. Use `st.cache_data` para histórico e previsão.
2. **Operação D+1.** Seletor de emissão `t0` (data e hora na grade de 30 minutos). Ranking de
   usinas em risco nas próximas 24 h: energia em risco, primeira janela de alerta, causa
   provável, confiança e ação sugerida. Perfil das 48 janelas da usina selecionada. Filtros por
   fonte, UF e subsistema. Previsões nulas aparecem como "sem evidência" com o motivo, nunca
   como zero.
3. **Visão tática.** Perdas históricas observadas por semana/mês, causa, UF e usina (as
   funções de agregação podem vir da Etapa 3; até lá, use o que for mínimo e testado).
4. **Metodologia e limites.** Obrigatório pelo `AGENTS.md`. Mostre fonte dos dados, janela
   temporal, corte de dados, momento da geração da previsão, tipo de saída (`baseline`,
   `modelo` ou `simulado`), incerteza e limitações. Um selo visível em todas as telas deve
   dizer quando a previsão é do preditor provisório `baseline`.
5. **Assistente contextual (opcional, só depois do resto).** Um resumo em texto gerado de forma
   determinística a partir das saídas estruturadas. Um provedor LLM (Bedrock ou NVIDIA NIM),
   se houver, fica atrás de uma interface, desligado por padrão, sem credenciais no repositório
   e só verbaliza números já calculados.

## Entregas da Etapa 5, preparação local (quinta-feira)

O acesso à AWS só existe de 25 a 27/09. Até lá, deixe tudo pronto para um deploy sem passos
manuais ocultos:

1. `Dockerfile` (Python 3.12 + `uv`) que roda o Streamlit na porta 8501, com health check em
   `/_stcore/health`. Os dados não entram na imagem: são montados ou baixados de S3 na
   inicialização, via `CURTAMAP_DATA_DIR`. Teste `docker build` e `docker run` localmente.
2. `infra/` com um app CDK mínimo: ECR, ECS Fargate atrás de um ALB (que suporta websockets),
   S3 para dados e CloudWatch Logs. Rode a CLI do CDK com `pnpm dlx aws-cdk` (nunca `npx`).
   `cdk synth` deve funcionar sem credenciais. Respeite as restrições de IAM de
   `docs/aws-environment.md`: papéis criados só podem ser passados a ECS, EC2, EFS e Bedrock;
   CodeBuild e Lambda usam o `WSParticipantRole`.
3. `docs/deploy.md` com o passo a passo do sábado e o plano de contingência: a demo local roda
   sem AWS e sem internet.

## Regras obrigatórias

- **TDD** para toda lógica fora da UI (filtros, rankings, formatação de episódios): teste
  primeiro, com limites, nulos, fonte diferente com o mesmo `id_ons` e usina sem evidência.
- **Teste reservado:** nunca leia, exiba ou use dados com `din_instante >= 2026-05-01`. O seletor
  de `t0` deve limitar a emissão a `t0 + 24h <= 01/05/2026`. O código já recusa esse período por
  padrão; não passe `allow_reserved_test=True`.
- Nenhum número simulado pode parecer real: todo mock tem rótulo visível.
- Novas dependências entram num extra próprio do `pyproject.toml` (por exemplo `infra`).
- Antes de cada commit: `uv run pytest`, `uv run ruff check .` e `uv run ruff format --check .`.
  No Windows, se `tests/test_feature_inventory.py` falhar por encoding, rode com
  `PYTHONUTF8=1`: é um problema conhecido e anterior a esta etapa.
- Verifique a interface rodando de verdade (`uv run streamlit run src/curtamap/app.py`), não só
  pelos testes.

## Encerramento

Acrescente uma entrada no fim de `docs/implementation-journal.md`, seguindo a estrutura de
oito itens definida no `AGENTS.md`, com capturas ou descrição do fluxo da demo. Faça push da
branch e informe ao responsável o que ficou pronto, o que ficou pendente e o que depende da
Etapa 3 ou do acesso à AWS.
