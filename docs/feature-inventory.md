# Inventário de campos contra vazamento temporal — Etapa 1

Este documento classifica **todos** os campos dos cinco Parquet do snapshot, os campos
extras da publicação atual do ONS e as colunas derivadas por `zelo.targets`. O teste
`tests/test_feature_inventory.py` falha se algum campo do contrato ou do alvo não estiver
classificado aqui, ou se aparecer uma classe fora da lista abaixo.

Nada aqui escolhe features ou algoritmos. O inventário define **o que pode ser usado e
com qual defasagem**; a seleção fica para a Etapa 2, com backtest temporal.

## Protocolo de previsão assumido

- Instante de emissão `t0` (as-of): a previsão é feita com o que estava **publicado e
  disponível** em `t0`, não com o que o arquivo atual contém sobre o passado.
- Horizonte operacional: **48 janelas de 30 minutos**, de `t0 + 30 min` até `t0 + 24 h`
  (arquitetura: previsão atualizada a cada 30 minutos, cobrindo as próximas 24 horas).
- Alvos por `fonte + id_ons + janela`: `restricao_registrada`, `corte_positivo`,
  `energia_mwh` condicional ao corte, e `causa`/`origem` (ver `target-definition.md`).
- Qualquer valor **verificado** de uma janela futura é pós-evento. Só pode entrar como
  defasagem, com `timestamp ≤ t0 − latência`.

## Classes

| Classe | Significado |
|---|---|
| identificador | Chave ou rótulo de entidade/tempo. Não é sinal preditivo por si só. |
| conhecida | Conhecida antes de `t0` para toda a janela futura: calendário, atributo cadastral estável. |
| defasagem | Só pode ser usada com atraso ≥ latência de publicação (nenhum campo é exclusivamente desta classe; ver coluna “Uso permitido”). |
| meteorologia futura | Previsão meteorológica emitida antes de `t0`, com timestamp de disponibilidade. **Não existe no snapshot.** |
| alvo | Variável a prever. Nunca é feature da mesma janela. |
| pós-evento | Medida ou decisão registrada durante/depois da janela. Proibida para a própria janela; permitida como defasagem. |
| auxiliar | Metadado, flag de qualidade ou campo técnico. Não é feature preditiva. |
| proibido | Vazamento estrutural: não usar como feature nem com defasagem ingênua. |

## Base principal e integrada (`constrained_off_*_tm.parquet`)

| Campo | Classe | Uso permitido | Justificativa |
|---|---|---|---|
| `fonte` | identificador | chave `fonte + id_ons`; indicador de tecnologia | `id_ons` isolado não é global. |
| `id_ons` | identificador | chave; efeito fixo de entidade com cuidado | Pode mudar de código (ex.: `BA4ECLA` → `CJU_BA4ECLA` na publicação atual de nov/2024). |
| `din_instante` | identificador | chave temporal; base do calendário | Sem fuso e sem definição de início/fim do patamar. |
| `nom_usina` | auxiliar | exibição | 18 IDs eólicos e 14 solares têm mais de um nome; não serve para join. |
| `ceg` | conhecida | nível conjunto (`-`) vs usina individual | Cadastral; valor conhecido antes da janela. |
| `id_estado` | conhecida | agregação regional, as-of | Cadastral. Sem mudança observada no snapshot, mas deve ser lido as-of. |
| `nom_estado` | auxiliar | exibição | Redundante com `id_estado`. |
| `id_subsistema` | conhecida | agregação sistêmica, as-of | Cadastral. |
| `nom_subsistema` | auxiliar | exibição | Redundante com `id_subsistema`. |
| `val_geracao` | pós-evento | somente defasagem (histórico próprio) | Geração verificada da janela futura; SCADA, alterável em pós-operação. |
| `val_geracaolimitada` | pós-evento | somente defasagem (ex.: limitação ontem no mesmo horário) | Limite em tempo real da janela; define o alvo de ocorrência. |
| `val_disponibilidade` | pós-evento | somente defasagem | Disponibilidade verificada; alterável em pós-operação. Extremo de 3,6 × 10⁶ MWmed exige tratamento antes de qualquer uso. |
| `val_geracaoreferencia` | pós-evento | somente defasagem | Referência ONS calculada para a janela; entra no alvo de volume. |
| `val_geracaoreferenciafinal` | proibido | nenhum no MVP | Específica de REL, calculada na apuração para a CCEE; mistura regra de liquidação com o alvo. |
| `cod_razaorestricao` | pós-evento | defasagem (ex.: causa dominante recente) | Causa registrada da janela; base do alvo `causa`. |
| `cod_origemrestricao` | pós-evento | defasagem | Origem registrada da janela; base do alvo `origem`. |
| `dsc_restricao` | pós-evento | defasagem, se for útil e auditado | Texto do evento na janela. |
| `ano` | conhecida | calendário | Derivado de `din_instante`; 0 divergências na auditoria. |
| `mes` | conhecida | calendário | Idem. |
| `data` | conhecida | calendário | Idem. |
| `hora` | conhecida | calendário | Idem. |
| `minuto` | conhecida | calendário | Idem. |
| `ano_mes` | conhecida | calendário | Idem. |
| `arquivo_origem` | auxiliar | rastreabilidade | Nome do arquivo de origem; não tem significado físico. |

## Detail por usina (`constrained_off_*_detail.parquet`)

| Campo | Classe | Uso permitido | Justificativa |
|---|---|---|---|
| `nom_modalidadeoperacao` | conhecida | segmentação cadastral | Atributo da usina. |
| `nom_conjuntousina` | auxiliar | investigação | Nome, não chave: o snapshot não traz `id_ons_conjuntousina`. |
| `val_ventoverificado` | proibido | análise histórica e defasagem explicitamente rotulada | Vento **verificado**, não previsão D+1. Contém extremo de 8,03 × 10²⁶. |
| `flg_dadoventoinvalido` | auxiliar | qualidade | Flag de medição. |
| `val_irradianciaverificado` | proibido | análise histórica e defasagem explicitamente rotulada | Irradiância **verificada**, não previsão D+1. Máximo de 123.312,404 W/m². |
| `flg_dadoirradianciainvalido` | auxiliar | qualidade | Flag de medição. |
| `val_geracaoestimada` | proibido | nenhum como feature futura | Derivada do vento/irradiância verificados da própria janela. |
| `val_geracaoverificada` | pós-evento | somente defasagem | Geração individual verificada. |

Os campos cadastrais comuns (`id_subsistema`, `id_estado`, `nom_usina`, `id_ons`, `ceg`,
`din_instante`, calendário e `arquivo_origem`) seguem a classificação da base principal.

## Campos extras da publicação atual do ONS (não existem no snapshot)

| Campo | Classe | Uso permitido | Justificativa |
|---|---|---|---|
| `val_geracaonaorealizadaapurada` | proibido | somente validação do alvo | É a GNRa publicada, ou seja, o próprio alvo. |
| `num_minutos_rel` | pós-evento | defasagem, se adotado | Duração da restrição na janela. |
| `num_minutos_cnf` | pós-evento | defasagem, se adotado | Idem. |
| `num_minutos_ene` | pós-evento | defasagem, se adotado | Idem. |
| `num_minutos_restricao` | pós-evento | defasagem, se adotado | Idem. |
| `id_pontoconexao` | conhecida | agrupamento elétrico, se incorporado | Cadastral; não está no snapshot. |
| `nom_pontoconexao` | auxiliar | exibição | Idem. |
| `nom_agenteoperador` | auxiliar | exibição | Idem. |

## Colunas derivadas pelo alvo (`zelo.targets`)

| Campo | Classe | Uso permitido | Justificativa |
|---|---|---|---|
| `restricao_registrada` | alvo | alvo de ocorrência (comando); defasagem como histórico | Limite não nulo, inclusive zero. |
| `corte_positivo` | alvo | alvo alternativo de ocorrência; defasagem | Volume > 0. |
| `volume_mwmed` | alvo | alvo de volume; defasagem | GNR analítica em MWmed. |
| `energia_mwh` | alvo | alvo de volume; defasagem | `volume_mwmed × 0,5`. |
| `causa` | alvo | alvo de causa; defasagem | Razão normalizada ou `DESCONHECIDA`. |
| `origem` | alvo | alvo de origem; defasagem | Origem normalizada ou `DESCONHECIDA`. |
| `energia_bruta_mwh` | auxiliar | sensibilidade | Inclui negativos finitos; não é alvo. |
| `entrada_negativa` | auxiliar | qualidade | Flag. |
| `entrada_nao_finita` | auxiliar | qualidade | Flag. |
| `entrada_ausente` | auxiliar | qualidade | Flag. |
| `volume_valido` | auxiliar | qualidade/filtro de avaliação | Flag. |
| `razao_desconhecida` | auxiliar | qualidade | Flag. |
| `origem_desconhecida` | auxiliar | qualidade | Flag. |
| `rotulo_sem_limite` | auxiliar | qualidade | Contradição entre rótulo e limite nulo. |

## Meteorologia futura

| Campo | Classe | Uso permitido | Justificativa |
|---|---|---|---|
| `previsao_meteorologica_asof` | meteorologia futura | somente com `emitida_em ≤ t0` registrado | Placeholder: não há previsão meteorológica no snapshot. ERA5 é reanálise, portanto verificada/retroativa, não previsão. |

## Regras obrigatórias para a Etapa 2

1. **Geração, limite, referência, disponibilidade, causa e origem da janela futura são
   pós-evento.** Só entram como defasagens do histórico próprio ou de agregados.
2. **Vento e irradiância do detail são verificados.** Podem apoiar diagnóstico histórico,
   mas não podem ser apresentados como feature D+1. Previsões meteorológicas futuras
   só entram com timestamp de emissão/disponibilidade (as-of).
3. **Latência de publicação ONS é desconhecida.** O snapshot não registra quando cada
   janela ficou disponível. Os baselines “último valor” e “mesmo horário do dia anterior”
   assumem latência zero, o que é otimista. A Etapa 2 deve declarar a latência adotada e
   medir a sensibilidade a cenários mais conservadores. Os valores dos cenários são
   hipóteses a validar, não fatos do ONS.
4. **Revisões pós-operação são vazamento potencial.** A comparação linha a linha
   (`official-comparison.json`, `revision_check`) mostrou 47 de 64 meses com diferença
   real entre o snapshot e a publicação atual, inclusive meses de 2023 regravados em
   setembro de 2026. Um backtest com dados revisados usa informação que não existia em `t0`.
   Isso deve ser registrado como incerteza. Não temos histórico de vintages para reproduzir
   a visão da época.
5. **Agregados regionais/sistêmicos** (UF, subsistema, total) herdam a classe dos campos
   agregados: agregado de geração ou limitação futura também é pós-evento.
6. **Cadastro muda.** Nome, código e agrupamento de conjuntos devem ser lidos as-of.
   Uma entidade com novo `id_ons` não herda histórico automaticamente.
