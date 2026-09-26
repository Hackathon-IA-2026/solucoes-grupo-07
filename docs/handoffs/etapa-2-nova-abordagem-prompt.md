# Prompt — Etapa 2 refeita do zero, com uma nova abordagem (sessão limpa, 26/09/2026)

Cole este documento inteiro no início de uma sessão nova do Claude Code, na raiz do
repositório, **no notebook** usado no evento presencial. Não é o computador dedicado onde a
Etapa 2 anterior rodou.

### 0. Primeiro passo: prepare a branch a partir da `main`

A `main` contém a Etapa 1 completa e o contrato de saída que permitiu paralelizar as Etapas 3 e
4. Ela **não** contém nada da Etapa 2 anterior, de propósito: nem código, nem datasets, nem o
protocolo. Comece do zero a partir dela:

```bash
git fetch origin
git status   # a árvore precisa estar limpa; se não estiver, pare e pergunte ao responsável
git switch -c etapa-2-nova-abordagem origin/main
# calendário de feriados com fontes oficiais, produzido na branch antiga (só dados):
mkdir -p configs
git show origin/etapa-2-experimental:configs/experimental/calendar-2023-2026.json > configs/calendario-2023-2026.json
git show origin/etapa-2-experimental:docs/handoffs/etapa-2-nova-abordagem-prompt.md > docs/handoffs/etapa-2-nova-abordagem-prompt.md
uv sync --dev
ls data/raw   # precisam existir os cinco Parquet do hackathon (ver §2, item 1)
```

- Faça o commit do calendário e deste prompt, em commits separados, como primeiros commits da
  branch.
- Se faltar algum Parquet em `data/raw/`, baixe com
  `uv sync --extra data --dev && uv run python -m curtamap.download_data` (ver
  `data/README.md`).
- Acrescente dependências (por exemplo, LightGBM) com `uv add` só se decidir usá-las.
- Meça a RAM e o disco livre do notebook antes de dimensionar qualquer treino.

---

## 1. Missão

Você vai refazer a modelagem do CurtaMap (Etapa 2) **do zero**, com um ângulo novo, num único
dia de trabalho contínuo (sábado, 26/09/2026). Domingo é o dia de unir as partes, containerizar
e apresentar. Ao fim de hoje, o produto precisa de um preditor melhor que o atual, avaliado
com honestidade e entregue no contrato de saída que as Etapas 3 e 4 já consomem.

**Decisão do responsável:** a receita atual não serve para o pitch. Só 2 das 6 células usam
modelo, as outras 4 usam baseline, e o ganho sobre o baseline é pequeno. **Não parta dela nem
faça pequenas variações dela.** Reaproveite só os **erros aprendidos** (§4) e a base
consolidada da Etapa 1 (§3). Leia o `AGENTS.md` e siga-o (TDD, diário, commits atômicos em
português, uv, Polars/DuckDB).

**Autonomia:** o desenho da nova abordagem é seu. As hipóteses do §5 são um ponto de partida
baseado em medições, não uma ordem. Se os dados indicarem outro caminho, siga os dados e
registre o porquê.

**Aviso sobre complexidade** (preocupação explícita do responsável): a primeira Etapa 2, desenhada
em grande parte por outro modelo, virou um pipeline de 100+ milhões de linhas, cerca de 50
features, picos de 33 GB e filas de horas, e ganhou pouco. Antes de cada decisão, pergunte-se
se o problema é tão complexo quanto parece. Comece pela solução mais simples que possa
funcionar e só acrescente complexidade com ganho medido. Também é possível que o problema seja
de fato complexo (setor elétrico, transição energética). Decida com evidência qual é o caso e
registre no diário.

## 2. O que já foi medido (fatos, 26/09 de manhã)

1. **A base real é pequena.** Em `data/raw/`, uma linha por usina e meia hora:
   - `constrained_off_eolica_tm.parquet`: 7.951.920 linhas, 172 usinas, de 10/2023 a 08/2026;
   - `constrained_off_fotovoltaica_tm.parquet`: 2.854.800 linhas, 81 usinas, de 04/2024 a
     08/2026;
   - os `*_detail` (63 M e 19 M linhas) trazem vento e irradiância **verificados** por
     usina, que não são previsão;
   - `constrained_off_eolica_fotovoltaica_tm.parquet` também existe (ver
     `src/curtamap/data_contract.py`).

   Os "100+ milhões" da Etapa 2 anterior vinham da expansão artificial em emissão ×
   horizonte, não dos dados.
2. **As 48 emissões por dia eram redundantes.** No cenário de liberação adotado (dados de um
   dia publicados às 19h30 do dia útil seguinte), as emissões de 00h a 19h do mesmo dia têm
   exatamente a mesma informação. Mesmo assim, 95% das features mudavam entre elas, porque
   as janelas de 7 e 28 dias andavam junto com `t0` sobre um período sem dados novos (medido
   em partições de 10/06 e 15/06/2026, solar e eólica). **Decisão do responsável:
   abandonar esse desenho.**
3. **O corte é essencialmente regional e sistêmico.** Contando só instantes com pelo menos 5
   usinas no estado:
   - eólica: 86% das meias-horas com corte positivo (88% do volume) acontecem quando a
     maioria das usinas do mesmo estado também está sendo cortada;
   - solar: 92% (93% do volume).
   - Prevalência de corte positivo: 26,9% na eólica e 19,3% na solar.
   - Causas registradas (linhas com limitação): eólica ENE 1,29 M, CNF 1,05 M, REL 0,21 M;
     solar ENE 0,48 M, CNF 0,17 M, REL 0,05 M.
4. **Informação disponível na previsão:** com a publicação diária às 19h30, uma emissão às
   20h do dia D conhece os dados até o fim de D−1 e prevê o dia D+1. A última observação
   fica, portanto, de 24,5 h a 48,5 h antes de cada janela prevista, **em dias úteis**.
   - Em fins de semana, feriados e segundas de manhã, a defasagem é maior, porque os dados de
     sábado e domingo só saem no dia útil seguinte. Numa segunda-feira (15/06/2026), a idade
     da última observação ia de 72,5 h a 88,5 h.
   - Qualquer feature de defasagem precisa respeitar essa idade variável.
   - **Não há previsão meteorológica** no snapshot. ERA5 e os `*_detail` são dados
     verificados ou reanálise.
   - O ONS publica o mês corrente diariamente: o S3 atualizou `..._2026_09.parquet` em
     25/09 às ~19h (horário de Brasília), o que é coerente com o cenário.
5. **Premissa mantida pelo responsável:** **não** supor que o gerador conheça em tempo real o
   corte da própria usina. Continua valendo a regra de publicação pública (liberação às 19h30
   do dia útil seguinte, com feriados em `configs/calendario-2023-2026.json` (§0).
6. **Dados novos para validação final:** o ONS já publicou setembro de 2026 (parcial) em
   `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_{eolica,fotovoltaica}_tm/RESTRICAO_COFF_{EOLICA,FOTOVOLTAICA}_2026_09.parquet`.
   Agosto também foi republicado em 25/09.
   - **Regra do responsável:** treinar e desenvolver **só com os dados fornecidos pelo
     hackathon** (`data/raw/`). Setembro serve **apenas** como validação final
     independente, aberta uma vez, no fim.
   - Não gaste tempo confirmando se os dados do hackathon são "tratados".
7. **Números da receita anterior no período de maio a agosto de 2026**, para contexto e não
   como alvo a imitar. Eram medidos por emissão de 30 em 30 minutos, então recalcule os
   baselines nas mesmas linhas do novo desenho antes de comparar:

   | Célula | Anterior (modelo ou baseline) | Melhor baseline |
   |---|---|---|
   | Corte solar | AP 0,875 | `historico` 0,824 |
   | Corte eólico | AP 0,828 (baseline); o modelo tinha 0,847 | — |
   | Volume solar | MAE 16,60 MWmed; o modelo tinha 14,56 | WAPE de cerca de 0,7 a 1,0 |
   | Volume eólico | MAE 20,10 MWmed | — |
   | Causa eólica | macro-F1 0,739 | `historico` 0,678 |
   | Causa solar | macro-F1 0,448 | — |

   O volume era o elo fraco, com o erro do tamanho do próprio volume.

## 3. O que reaproveitar (Etapa 1 consolidada) e o que entregar

- **Alvo:** `docs/target-definition.md` e `src/curtamap/targets.py` (`derive_targets`,
  testado).
  - Volume = máx(referência − geração, 0) quando há limitação; energia = MWmed × 0,5.
  - O corte positivo é a ocorrência principal.
  - Chave `fonte + id_ons`.
  - 21 volumes eólicos negativos ficam indeterminados.
  - Causa só existe sob limitação (`REL`, `CNF`, `ENE`); `PAR` não tem suporte e
    `DESCONHECIDA` não é causa.
- **Auditoria e contrato de dados:** `docs/reports/stage1/audit.md`, `docs/data-contract.md`,
  `src/curtamap/data_contract.py`.
- **Calendário e feriados:** `configs/calendario-2023-2026.json` (§0).
- **Preditor provisório:** `src/curtamap/forecasting.py` (mesmo horário recente) já gera o
  contrato. Serve de referência de formato e de baseline.
- **Contrato de saída obrigatório:** `FORECAST_SCHEMA` em `src/curtamap/contracts.py` da
  `main`, idêntico ao da branch `etapa-3-recomendacao`.
  - A unidade é `fonte + id_ons + t0 + horizonte` (1..48, meia hora). Uma emissão diária
    atende ao contrato.
  - Colunas de probabilidade, alerta, volume esperado com p10/p90, causa com `p_causa_*`,
    origem e proveniência (`tipo_saida` modelo/baseline/simulado, `modelo_id`,
    `corte_dados` e outras).
  - A recomendação (Etapa 3) e a interface Streamlit (`origin/etapa-4-interface`) consomem
    só esse formato.
- **Não reaproveite** nada da Etapa 2 anterior. Os erros que importam estão resumidos no §4.
  Consulte `origin/etapa-2-experimental` só se precisar do detalhe de um erro específico. O
  diário completo está lá, em `docs/implementation-journal.md`; o da `main` vai só até a
  Etapa 1 e o plano paralelo. Crie um módulo novo, por exemplo `src/curtamap/previsao/`.

## 4. Erros aprendidos (não repita)

1. **Expansão emissão × horizonte:** foi a causa de memória, amostragem e lentidão. A unidade
   natural é a usina × a meia hora do dia seguinte, emitida uma vez por dia.
2. **Features demais e desalinhadas:** na 2B, os modelos receberam 12 features erradas (sem
   hora do dia) e perderam para o baseline. Depois vieram cerca de 50 features com ganho
   pequeno. Na `s01`, 8 variáveis obtiveram a maior parte do ganho. **Poucas features, com
   significado físico e operacional.**
3. **Sazonalidade falsa:** com menos de dois anos de solar, `mês` e `dia do ano` ensinam
   tendência como estação. Retirá-los melhorou tudo.
4. **Mudança de regime:** a prevalência de corte solar dobrou em maio–agosto de 2025. O
   calibrador congelado subestimou o nível, e a recalibração semanal testada embaralhou o
   ranking entre semanas (reprovada). Mostre a robustez por período.
5. **Baselines fortes:** a frequência histórica da própria usina naquele horário
   (`historico`) é difícil de bater. O "mesmo horário do dia anterior" quase sempre cai no
   fallback, por causa da defasagem de 24,5 a 48,5 h. Compare sempre com pelo menos
   `último valor disponível`, `mesmo horário do último dia disponível` e uma frequência
   histórica por usina × hora, **nas mesmas linhas**.
6. **Volume:** o pipeline Gamma `P × condicional` explodiu (MAE 37,8 contra 13,6). As
   categóricas nativas do LightGBM quebraram o treino de volume
   (`best_split_info.left_count > 0`). Tweedie com offset funcionou, mas pouco.
7. **Operacional:**
   - o Claude Code encerra shells em segundo plano sob pressão de memória. Isso aconteceu no
     computador dedicado, de 32 GB, com picos de 21 a 33 GB. Use `nohup` em treinos longos e
     prefira trabalhos que caibam com folga na RAM do notebook;
   - a ordem de linhas do Polars *streaming* não é determinística: ordene por chave depois
     de `collect`;
   - nunca rode `git clean -x`.
8. **Processo:** o protocolo pré-registrado com rodadas V1–V4 e filas de horas deu rigor, mas
   foi lento demais para um hackathon. Hoje: **iterações de minutos**, validação temporal
   simples e decisões registradas em poucas linhas antes de ver o resultado.

## 5. Hipóteses de partida (meça, não assuma)

- **H1, de cima para baixo:** como mais de 85% do corte é simultâneo no estado, prever o
  evento regional (estado ou subsistema × meia hora do dia seguinte) é um problema pequeno e
  de sinal forte. A usina herda a probabilidade regional ajustada pela sua propensão
  histórica (participação no volume, frequência relativa). Compare com a modelagem direta por
  usina.
- **H2, o nível diário antes da forma intradiária:** decompor em "quanto corte o dia
  seguinte terá" (nível) e "em que horas" (perfil por hora, dia da semana ou feriado e
  fonte). O perfil solar é quase determinístico: só existe corte com sol.
- **H3, a métrica de negócio:** o gerador planeja por dia. Reporte também o erro em MWh por
  usina × dia (WAPE diário), além da meia hora. **Não troque a métrica para esconder erro:**
  reporte as duas.
- **H4, sinais sistêmicos do próprio dataset:** a geração de referência agregada da região no
  último dia disponível, a fração de usinas cortadas e a causa dominante recente (ENE está
  ligada a excedente de energia e carga baixa: fins de semana, feriados e meio-dia solar).
- **H5, opcional e com rótulo explícito:** um experimento "oráculo" com vento e irradiância
  verificados, para medir **quanto valeria** uma previsão meteorológica. Nunca como feature
  D+1 do produto. Serve ao pitch ("com um feed de previsão, ganha-se X"). Só faça se sobrar
  tempo.

## 6. Avaliação

- **Desenvolvimento:** só `data/raw/` (até 31/08/2026), com validação temporal com origem
  expandindo (por exemplo, dobras mensais nos últimos 6 a 8 meses). Nunca split aleatório.
  - Maio a agosto de 2026 já foi visto pela receita anterior. Para a nova abordagem, pode
    ser dobra de desenvolvimento, e isso deve ficar declarado.
- **Validação final independente, uma única vez:** setembro de 2026 do S3 do ONS.
  - Antes de abrir, congele a receita num commit com previsões escritas.
  - Atenção às diferenças da publicação atual (`''` em vez de `NULL` e outras, em
    `docs/target-definition.md`).
  - O histórico usado como feature em setembro pode vir de `data/raw/` até 31/08, mais os
    dias de setembro já liberados em cada emissão.
- **Trava do período reservado:** a `main` tem `RESERVED_TEST_START = 2026-05-01` em
  `src/curtamap/contracts.py`, usada por `src/curtamap/forecasting.py` e
  `tests/test_forecasting.py`. A `etapa-3-recomendacao` também protege a suíte contra esse
  período.
  - Esse período foi consumido em 25/09, e o novo teste independente é setembro de 2026.
  - Atualize a constante (por exemplo, `2026-09-01`) e os testes ou validadores que a usam num
    commit dedicado e registrado no diário.
  - Avise essa mudança no handoff de domingo, para a integração com as Etapas 3 e 4.
  - Sem isso, a sessão falha nos testes ou deixa de usar os dados mais recentes na demonstração.
- **Poder estatístico de setembro:** são cerca de três semanas. Reporte setembro também semana
  a semana e não trate um número isolado como conclusivo.
- **Métricas:** PR-AUC e recall no evento, com calibração (Brier); MAE e WAPE no volume, na
  meia hora e no dia; macro-F1 na causa. Sempre contra os baselines, nas mesmas linhas, com
  quebra por mês.
- **Critério de sucesso para o pitch:** o modelo vence os baselines de forma clara e estável na
  maioria das seis células (fonte × corte/volume/causa), ou um resultado honesto que explique
  por que não.

## 7. Entregáveis de hoje

1. Um módulo novo testado, que gera `FORECAST_SCHEMA` para uma emissão diária.
2. Um relatório curto em `docs/reports/nova-abordagem/`: desenho, resultados por célula
   contra os baselines, setembro e limitações.
3. Entradas no `docs/implementation-journal.md` (append-only, estrutura do `AGENTS.md`),
   incluindo a análise "problema simples ou complexo?".
4. Um recorte leve de reprodução histórica para o dashboard, no contrato: poucas semanas, com
   emissão diária às 20h e verdade observada ao lado. Ele fica fora do Git e é regenerável por
   um script versionado.
5. Um handoff atualizado para domingo (integração e containerização).

Commits atômicos e frequentes. Merge em `main` não autorizado sem pedido.

## 8. Trabalho contínuo sem interrupção (instrução do responsável, na íntegra)

> Apenas uma estratégia que a gente pode utilizar para garantir que você consiga trabalhar
> praticamente o dia todo sem interrupções é que a janela de cache costuma esgotar em uma
> hora. Então, se você ficar muito tempo sem trabalhar em nada, isso pode acontecer. E aí,
> quando você voltar, ela vai estar esgotada e vai custar muito na janela de 5 horas. E aí
> pode ser que você seja interrompido e não consiga fazer o trabalho continuamente.
>
> Portanto, você pode trabalhar à vontade. Não é questão de diminuir a velocidade do seu
> trabalho, mas toda vez que você tiver que esperar alguma ação, seja de espera de
> treinamento, qualquer coisa, ou alguma resposta minha, coloque um monitorador de timer de
> no máximo 50 minutos. Para caso você não receba nenhuma resposta nesse meio tempo, você
> volte a fazer alguma coisa.
>
> Para a questão de perguntas para mim, eu vou acabar recebendo a notificação no meu celular.
> Então esse é um problema um pouco menor, mas ainda existe o caso onde eu não consiga ver no
> momento e acabe perdendo a mensagem por um tempo. Por conta disso, faça esse esquema do
> monitoramento de no máximo 50 minutos, porque assim obrigatoriamente você vai voltar a
> fazer alguma coisa antes de uma hora e a janela de cache não é invalidada.
>
> Você também pode fazer isso toda vez que achar que vai parar algum trabalho: coloca esse
> monitoramento de 50 minutos. Mas se talvez um monitoramento de uma sessão de treinamento ou
> de recalibração voltar, você pode cancelar esse monitoramento dos 50 minutos. A ideia é que
> ele só exista enquanto você realmente está esperando. Quando você voltar a fazer trabalho,
> você o cancela e só volta com ele quando voltar a esperar.
>
> Dessa forma, você pode trabalhar continuamente o dia todo para a gente tentar melhorar o
> máximo possível o modelo. E amanhã a gente só une todas as partes e começa o trabalho da
> containerização.

**Como aplicar:**

- Para esperar, use `Bash` com `run_in_background: true` e `sleep 2880`: você é reinvocado
  quando ele termina. Pare-o com `TaskStop` ao voltar a trabalhar por outro motivo.
- Ao fazer uma pergunta, arme o timer. Se ele expirar sem resposta, siga com a opção
  recomendada que não seja irreversível e registre isso no diário.
- Só pergunte o que for de fato decisão do responsável.
