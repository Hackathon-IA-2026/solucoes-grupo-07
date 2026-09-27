# Revisão metodológica externa — 19/09/2026

Modelo confirmado: `claude-opus-5`; `--effort high`; ferramentas somente Read; sem edição.
Abaixo está feedback, não evidência quantitativa.

O plano está bem encaminhado, mas algumas correções precisam vir antes de implementar. Não consegui abrir `docs/sources/*.json` porque não tenho como listar o diretório. Por isso, não conferi o link do detail eólico.

## P0: bloqueiam o alvo e a auditoria

1. **"Ocorrência = limite não nulo" mistura duas coisas.** Uma é a restrição registrada, a outra é o corte que de fato aconteceu. Um limite acima da referência, ou com referência menor ou igual à geração, não corta nada. Separe dois rótulos: `restricao_registrada` e `corte_efetivo` (energia > 0). O regressor de volume deve ser condicionado a `corte_efetivo`, não ao limite. Teste: limite zero com referência zero, limite maior que a referência e referência menor que a geração.
2. **Falta de linha não é "fora = 0".** Só use 0 quando a linha existe e o limite é nulo com os demais campos válidos. Janela ausente continua ausente, sem zero. O mesmo vale para limite nulo por falha de dado, que precisa ser distinguível de "sem restrição". Teste: grade com lacuna, que não pode virar zero.
3. **Qual referência entra na fórmula?** Se existem mais de uma variante de referência, fixe uma, cite o trecho do dicionário e teste. A GNRa não existe localmente, então "mesma fórmula" é hipótese e não validação: registre assim no diário e no dashboard.
4. **Semântica de `din_instante` e fuso horário.** Defina se o instante marca o início ou o fim da janela. Verifique o horário de verão anterior a 2019: horas duplicadas ou faltantes quebram a continuidade e a chave. Teste as transições de horário de verão na checagem de continuidade.
5. **A quarentena de negativos contradiz o AGENTS.md** ("não transforme hipótese em regra sem evidência"). A geração noturna solar levemente negativa pode ser comum. Primeiro audite com uma flag, sem excluir linhas. A quarentena só entra depois de medir o impacto, e a decisão vai para o diário.
6. **Proveniência do JSON detail eólico.** Corrija antes de usar o arquivo e registre checksum e fonte. Sem isso, a comparação detail x principais não vale nada.

## P1: correção da comparação e da EDA

7. **Integrada x UNION ALL.** Faça anti-join nos dois sentidos pela chave completa. Compare valores com `IS NOT DISTINCT FROM` e tolerância numérica. Harmonize os tipos antes (float/decimal, timestamp com ou sem fuso). Contar linhas não basta.
8. **Detail x principais.** Documente o mapeamento de granularidade entre as tabelas e teste que o join não multiplica linhas (cardinalidade esperada, 1:N explícito).
9. **Consistência entre causa e limite.** Uma causa preenchida sem limite é inconsistência e precisa de uma categoria própria, que não deve ser misturada com "desconhecida".
10. **Estabilidade do `id_ons` no tempo.** Verifique reuso ou renomeação: a mesma chave não pode mudar de usina, UF ou subsistema.
11. **Painel fixo.** Defina o critério de entrada no painel antes de olhar os resultados, para não escolher o painel pelo resultado.
12. **Episódios.** Teste explicitamente o comprimento máximo de lacuna igual a 0 e a quebra na troca de entidade.

## P1: vazamento temporal no D+1

13. **O próprio histórico ONS de restrição também tem latência de publicação.** Os baselines "último valor" e "mesmo horário do dia anterior" precisam de um as-of declarado. Se a latência for desconhecida, rode também um cenário com defasagem conservadora.

## P2: operacional

14. **Configuração do DuckDB.** Defina `temp_directory`, `preserve_insertion_order=false` e `memory_limit` explícito. Marque se os quantis são aproximados ou exatos.
15. **Rastreabilidade da auditoria.** Registre versão, checksum dos Parquet e as queries SQL versionadas junto dos agregados que o notebook consome.

## Testes mínimos indispensáveis (TDD do alvo)

- Limite nulo com linha válida dá 0; linha ausente fica ausente.
- Limite zero conta como restrição, mas só é corte se a referência for maior que a geração.
- Referência menor que a geração dá 0, sem valor negativo.
- NaN ou infinito na referência ou na geração, quando há restrição, dão energia nula e uma flag.
- A conversão MWmed × 0,5 = MWh aparece em um caso numérico conhecido.
- Causa nula com restrição vira `DESCONHECIDA`; causa sem restrição vira flag de inconsistência.
- A chave `fonte + id_ons + din_instante` é única, inclusive nas transições de horário de verão.

## Decisões do orquestrador

Aceitos: distinguir comando/volume positivo, preservar lacunas, testar NaN/infinito,
verificar identidade e contradições de rótulo, documentar latência e painel.
Negativos foram medidos antes de definir energia indeterminada; originais preservados.
Não aceitamos substituir automaticamente o alvo de ocorrência ou dizer que a fórmula
é apenas hipótese: o dicionário atual define GNRa e a comparação pública posterior
reproduziu 3.127.621 valores. Nem isso valida compensação financeira ou todos os totais.
Horário de verão anterior a 2019 está fora do período local, mas fuso continua pendente.
A revisão de código final pelo Opus ainda não foi realizada.

## Triagem item a item — segunda passagem (19/09/2026)

Metadado conferido em `tmp/review-methodology.json` (local, não versionado): `modelUsage`
registra apenas `claude-opus-5`, 4 turnos e nenhuma negação de permissão. O esforço `high` e o
modo somente leitura constam do comando registrado acima. O revisor não editou arquivos.

| # | Sugestão | Decisão | Como foi tratada |
|---|---|---|---|
| 1 | Separar restrição registrada de corte efetivo | **Adaptada** | Os dois alvos existem (`restricao_registrada`, `corte_positivo`). Não substituímos o alvo de ocorrência: a escolha fica para a Etapa 2. A EDA mediu que 18%/22% das limitações têm volume zero. |
| 2 | Linha ausente não vira zero | **Aceita** | `derive_targets` não cria linhas; teste de grade incompleta; episódios e persistência quebram em lacunas. |
| 3 | Fixar a referência e tratar a fórmula como hipótese | **Parcialmente rejeitada** | A referência comum foi fixada e a final REL rejeitada como alvo universal. Não é “só hipótese”: o dicionário define a GNRa e a fórmula reproduz 3.127.621 valores publicados. A equivalência de totais continua provisória. |
| 4 | Semântica de `din_instante`, fuso e horário de verão | **Aceita como limitação** | Não há metadado de fuso ou convenção no Parquet nem no dicionário. Não existe horário de verão no período. Registrado no notebook, no contrato e no inventário. |
| 5 | Não fazer quarentena de negativos sem medir | **Aceita** | Os negativos foram medidos antes (29 gerações, 1 limite). Volume nulo e flag só quando há limitação; a variante bruta vai para a sensibilidade; os originais são preservados. |
| 6 | Proveniência do JSON detail eólico | **Aceita** | A inconsistência JSON × URL está registrada; o PDF foi conferido; o JSON não foi usado como schema. |
| 7 | Integrada × união por multiconjunto com tolerância | **Adaptada** | `EXCEPT ALL` em todas as colunas, com igualdade exata (mais estrita que tolerância) e particionado por mês sem perder semântica. Os tipos são iguais pelo contrato. |
| 8 | Detail × principais sem multiplicar linhas | **Aceita** | `duplicated_join_rows` foi adicionado e testado; resultado 0 no snapshot. |
| 9 | Causa sem limite como categoria própria | **Aceita** | `rotulo_sem_limite` é separado de `razao_desconhecida`/`origem_desconhecida`; `''` não conta como rótulo. |
| 10 | Estabilidade do `id_ons` | **Aceita** | `identity_drift`, agora sensível a `NULL`. Uma renomeação de código foi encontrada só na publicação atual (`BA4ECLA` → `CJU_BA4ECLA`). |
| 11 | Painel fixo definido antes dos resultados | **Aceita** | Regra codificada em `zelo.eda` (cobertura completa abr–ago nos 3 anos e volume válido) e descrita como retrospectiva. |
| 12 | Episódios: lacuna zero e troca de entidade | **Aceita** | Testes em `tests/test_eda.py` cobrem lacuna, zero, desconhecido, entidade e fonte. |
| 13 | Latência de publicação e as-of dos baselines | **Aceita (Etapa 2)** | `docs/feature-inventory.md` exige latência declarada e cenários conservadores. As revisões medidas reforçam o risco. |
| 14 | Configuração DuckDB e quantis aproximados | **Parcialmente aceita** | `memory_limit`, `threads` e `preserve_insertion_order` estão explícitos; os quantis estão marcados como aproximados. `temp_directory` fica no padrão do DuckDB (`.tmp/`, ignorado pelo Git). |
| 15 | Rastreabilidade: versão, checksum e SQL | **Aceita** | O JSON registra SHA-256 e versão DuckDB; o SQL está versionado no código; o notebook confere o SHA-256 antes de analisar. |
