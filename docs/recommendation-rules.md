# Regras de recomendação e cenários de impacto — versão 1

> **Revisão posterior em 23/09/2026:** a versão 1 abaixo é histórica. A corrigenda ao final
> substitui os números do exemplo, a convenção de capacidade e as conclusões regulatórias
> excessivas. O padrão executável agora é `premissas_v2`.

## Escopo e linguagem de segurança

Estas regras transformam uma previsão validada em uma orientação para conferência humana. Elas
não comandam a usina, não substituem mensagens do ONS e não afirmam que energia cortada será
recuperada. `energia_recuperavel_mwh`, `valor_estimado_brl` e `co2_evitado_t` são **cenários**:
dependem do ativo realmente instalado, do estado de carga, da conexão, do contrato, da regulação e
da autorização operacional.

Os códigos têm a semântica publicada pelo ONS: REL é indisponibilidade externa; CNF é atendimento
a requisitos de confiabilidade elétrica; ENE é impossibilidade de alocar geração na carga; PAR é
restrição vigente indicada no parecer de acesso. O ONS também informa que os comandos chegam ao
agente via SINapse e podem mudar de motivo e valor ao longo do dia. Fontes: [NT-ONS DOP
0022/2025](https://www.ons.org.br/AcervoDigitalDocumentosEPublicacoes/NT-ONS%20DOP%200022.2025%20-%20Crit%C3%A9rios%20para%20Gest%C3%A3o%20de%20Excedentes%20Energ%C3%A9ticos.pdf),
seções 6 e 7; [RO-AO.BR.13 Rev. 08](https://www.ons.org.br/%2FMPO%2FDocumento%20Normativo%2F4.%20Rotinas%20Operacionais%20-%20SM%205.13%2F4.3.%20Rotinas%20P%C3%B3s-Opera%C3%A7%C3%A3o%2F4.3.2.%20Apura%C3%A7%C3%A3o%20de%20Dados%2FRO-AO.BR.13_Rev.08.pdf).
Consulta: 23/09/2026.

## Da janela prevista ao episódio

Janelas de 30 minutos com `alerta = True` são ordenadas e agrupadas quando são consecutivas dentro
da mesma chave `fonte + id_ons + t0`. Uma janela sem alerta, uma lacuna temporal, outra fonte ou
outra emissão `t0` inicia novo episódio. `fim` é o limite direito exclusivo da última janela e
`energia_em_risco_mwh` é a soma da energia esperada somente daquela emissão. O código recusa um
alerta com energia nula em vez de produzir uma soma parcial.

Se todas as janelas do episódio tiverem a mesma causa não nula, ela vira `causa_base`. Se houver
causa nula ou mudança de causa, `causa_base` fica nula: o Zelo não elege uma causa dominante.
Isso é conservador porque o próprio ONS registra que a classificação pode mudar ao longo do dia.

## Matriz causa → ação

| Causa | Ação determinística | Antecedência e diferença por fonte | Limite operacional/regulatório | Natureza |
|---|---|---|---|---|
| REL | `PRESERVAR_EVIDENCIAS_ESS`: confirmar mensagem, preservar telemetria e preparar conferência da apuração | Assim que o alerta surgir. Eólica: conferir vento e curva de produtividade. Solar: conferir irradiância e função de produtividade, especialmente em horas de sol | Não elevar geração contra o limite. ONS calcula referência final para REL; eventual ESS depende da apuração e das regras vigentes, não da previsão | Fato regulatório para a apuração; utilidade antecipatória é hipótese de produto |
| CNF | `COORDENAR_OPERACAO`: alinhar centro de operação e, se possível, deslocar manutenção flexível | Assim que o alerta surgir; revalidar a cada mensagem. Em solar, a janela útil termina com a irradiância; em eólica, o recurso pode persistir à noite | Segurança elétrica prevalece. Não há recuperação autônoma nem receita pressuposta | Limite é fato ONS; deslocar manutenção é hipótese a validar com o gerador |
| ENE | `AVALIAR_ARMAZENAMENTO`: simular carga de bateria e descarga posterior | Antes de `inicio`, usando a antecedência exibida. Solar tende a concentrar oportunidade diurna; eólica pode incluir noite | Só vale com bateria instalada/habilitada, potência, capacidade e estado de carga disponíveis, conexão e comando compatíveis. A descarga futura também precisa ser possível | Existência de armazenamento como flexibilidade é fato setorial; uso atrás desta recomendação é cenário |
| PAR | `REVISAR_PARECER_ACESSO`: conferir limite e priorizar estudo de conexão/reforço | No planejamento e antes da janela; não é correção em tempo real | A limitação consta do parecer de acesso. O cenário de recuperação imediata é zero até existir solução aprovada | Definição é fato ONS; escolha de priorização é decisão de produto |
| nula/desconhecida | `VALIDAR_CAUSA`: confirmar a mensagem do ONS antes de qualquer resposta específica | Imediatamente, mostrando explicitamente “causa indeterminada” | Proibido inferir causa pelo volume, fonte ou origem | Decisão conservadora do Zelo |

Para REL, a [REN ANEEL nº 1.030/2022](https://www2.aneel.gov.br/cedoc/ren20221030.html) e o
procedimento do ONS delimitam o tratamento do constrained-off e da apuração. A NT do ONS informa
que, para pagamento de ESS pela CCEE, a geração de referência final é calculada para eventos REL.
Logo, o Zelo nunca aplica PLD diretamente para afirmar ressarcimento.

## Origem LOC/SIS

`origem_prevista` não muda o limite operativo nem cria direito financeiro. Ela apenas direciona a
conferência: LOC sugere envolver primeiro a operação regional e conferir restrições/inequações
locais; SIS sugere acompanhar mensagens e condições sistêmicas. Se a origem variar ou faltar, ela
não é incorporada à regra. Essa priorização de fluxo de trabalho é **hipótese de produto**; precisa
ser validada com operadores. O ONS descreve controles regionais e sistêmicos nos itens 6.2.1 e
6.2.2 da NT-ONS DOP 0022/2025.

## Premissas versionadas

O arquivo [`configs/premissas/v1.json`](../configs/premissas/v1.json) registra valor, unidade,
fonte, URL e data de consulta para cada número. `premissas_versao = premissas_v1` identifica o
arquivo usado.

| Premissa | Baixo | Base | Alto | Fonte e interpretação |
|---|---:|---:|---:|---|
| Preço de energia (R$/MWh) | 58,60 | 310,29 | 751,73 | CCEE: piso, expectativa média de junho/2025 para SE/CO, NE e N, e teto de 2025. É proxy de sensibilidade, não preço contratual nem receita garantida |
| Fator da margem de operação (tCO₂/MWh) | 0,2146 | 0,4124667 | 0,5780 | MCTI 2025: mínimo mensal, média aritmética dos 12 meses e máximo mensal. Serve a cenário de emissão deslocada; não é inventário corporativo nem redução certificada |
| Potência da bateria (MW) | 30 | 30 | 30 | Requisito mínimo publicado pelo MME para o LRCAP Armazenamento 2026; referência setorial, não ativo presumido da usina |
| Duração/capacidade | 4 h / 120 MWh | 4 h / 120 MWh | 4 h / 120 MWh | MME: operação contínua mínima por quatro horas; 120 MWh é derivado de 30 MW × 4 h |
| Eficiência total | 85% | 90% | 90% | 85% é o mínimo do LRCAP; 90% é premissa de ciclo do PDE 2030 da EPE |

Fontes consultadas em 23/09/2026:

- [CCEE — InfoBandeira Tarifária, junho/2025](https://www.ccee.org.br/documents/80415/30094498/86%20-%20InfoBandeira%20Tarif%C3%A1ria_2025_06.pdf/d2abc6e2-fa3e-43f5-02d4-12bfde14c070).
- [MCTI — fatores da margem de operação do SIN, ano-base 2025](https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/sirene/dados-e-ferramentas/fatores-de-emissao/arquivo/Despacho_2025_jandez_corrigidacomMO.xlsx).
- [MME — diretrizes do LRCAP Armazenamento 2026](https://www.gov.br/mme/pt-br/assuntos/noticias/mme-publica-diretrizes-para-leilao-inedito-de-armazenamento-de-energia-em-baterias-no-brasil).
- [EPE — PDE 2030](https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-490/PDE%202030_RevisaoPosCP_rv2.pdf), premissa de eficiência de ciclo de 90%.

O cenário ENE usa:

```text
entrada possível = min(energia em risco, potência × duração do episódio, capacidade)
energia recuperável = min(energia em risco, entrada possível × eficiência)
valor indicativo = energia recuperável × preço do cenário
CO₂ indicativo = energia recuperável × fator da margem de operação do cenário
```

As demais ações têm `energia_recuperavel_mwh = 0` nesta versão: não há premissa defensável que
transforme conferência, coordenação ou estudo em energia recuperada. Se faltar potência,
capacidade ou eficiência, a recuperação também é zero; se faltar preço ou fator de emissão, o
respectivo resultado é nulo. Zero significa “nenhuma recuperação quantificada por esta versão”,
não “a ação não tem valor”.

## História para validação com o gerador

Esta é uma **emissão reconstituída**, reproduzível com dados reais do desafio anteriores ao teste
reservado; não é registro de uma decisão tomada por um operador. Em 29/04/2026 às 10h, com corte
de disponibilidade em 28/04/2026 às 00h, o baseline
`baseline_mesmo_horario_recente_v1` produziu para a entidade fotovoltaica `CJU_MGARN` um episódio
ENE de 12h às 14h — duas horas de antecedência — com 148,14 MWh em risco.

O gerador vê fonte, entidade, emissão, janela, causa ENE, 148,14 MWh e a ação “avaliar
armazenamento”. Antes das 12h, ele confere a mensagem do ONS, o estado de carga e os limites do
ativo. Se — e somente se — dispuser do sistema de referência de 30 MW/120 MWh e puder carregá-lo
durante as duas horas, a sensibilidade mostra:

| Cenário | Energia recuperável | Valor indicativo | CO₂ indicativo |
|---|---:|---:|---:|
| Baixo | 51,00 MWh | R$ 2.988,60 | 10,9446 tCO₂ |
| Base | 54,00 MWh | R$ 16.755,66 | 22,2732 tCO₂ |
| Alto | 54,00 MWh | R$ 40.593,42 | 31,2120 tCO₂ |

Ele pode decidir reservar capacidade e pedir validação operacional; não pode concluir que os
54 MWh serão recuperados, vendidos ao PLD, ressarcidos ou certificados como redução de emissões.
O Zelo também não garante que a causa continuará ENE, que haverá espaço para descarga futura
ou que esse conjunto do ONS corresponda a uma única usina física. O valor para o pitch é mostrar
a passagem rastreável de previsão → regra → premissa → cenário → limite, sem transformar hipótese
em promessa.

## Resumo tático observado

`summarize_history` chama `derive_targets` e agrega dados reais por fonte, entidade, semana/mês,
causa, UF e subsistema. As saídas são `janelas_observadas`, `janelas_com_corte` e
`energia_observada_mwh`; não são previsão. A função recusa qualquer linha com
`din_instante >= 2026-05-01` enquanto o teste reservado estiver protegido.


## Corrigenda posterior — auditoria de 23/09/2026

Esta seção corrige, sem apagar, o registro v1 acima. Fundamentação, linhas de código, fonte de
cada número, roteiro humano e handoff completo: [auditoria da Etapa 3](reviews/astra-stage3-audit.md).

### Regulação e utilidade das ações

A definição publicada de `val_geracaoreferenciafinal` continua específica de REL nos dicionários
ONS consultados. Isso **não demonstra que somente REL possa ensejar ESS/compensação**.
A [Lei 10.848/2004 consolidada](https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l10.848.htm),
art. 1 §§10–11 e art. 1º-B, inclui tratamento e condições envolvendo confiabilidade.
A [CCEE informou mudanças em regras solares em junho/2026](https://www.ccee.org.br/en/web/guest/-/co-ccee-disponibiliza-novas-versoes-de-regras-de-comercializacao-referentes-ao-constrained-off-de-usinas-solares-fotovoltaicas-ren-1.158-2026).
O código não calcula direitos: REL/CNF devem preservar evidências e buscar avaliação específica
do período, agente, contrato, acesso e conformidade. ENE/PAR tampouco geram promessa financeira.

LOC/SIS é uma taxonomia confirmada; seu direcionamento regional é hipótese de fluxo de trabalho,
não competência ou direito financeiro. O backend só exibe a origem quando uniforme. As diferenças
operacionais por fonte e a sugestão de manutenção precisam das entrevistas, ainda não realizadas.
A antecedência é `inicio−t0`, não prazo garantido de execução.

### Premissas v2 e energia por intervalo

O padrão passou a [`v2.json`](../configs/premissas/v2.json); v1 permanece para reprodução.
R$ 751,73 é teto **estrutural** de 2025. A média de PLD foi reproduzida com 720 horas de junho/2025;
os fatores MCTI foram recalculados em células corrigidas da planilha 2025. Esses números são
referências históricas de sensibilidade, não previsões para o episódio de abril/2026.

A [Portaria MME 136/2026](https://www.gov.br/mme/pt-br/acesso-a-informacao/legislacao/portarias/2026/portaria-normativa-mme-n-136-2026.pdf)
define requisitos de leilão e compromisso de energia entregável. Na v2, 120 MWh representam
capacidade **útil de saída disponível**; a potência de **carga** de 30 MW é hipótese adicional.
90% está documentado no PDE 2030 p.294, em estudo de geração distribuída; não é garantia de RTE
para bateria centralizada. Não presumir ativo, SOC ou descarga viável.

```text
entrada = Σ min(energia da meia-hora, potência de carga × 0,5 h)
recuperável = min(energia total em risco, entrada × RTE, capacidade útil de saída)
```

`build_recommendations` sempre passa `energia_por_janela_mwh` a `impact_sensitivity` pelo argumento
`energy_profile_mwh`. Chamar a função de impacto sem esse perfil calcula apenas um teto agregado;
não fazer isso para mostrar a sensibilidade de uma recomendação real.

Correção do exemplo: `[26/04/2026, 28/04/2026)` reproduz, na emissão 29/04 às 10h, o episódio
`fotovoltaica + CJU_MGARN` de 12h–14h. Energias por meia hora: 2,9865 / 83,5655 / 61,4625 /
0,1255 MWh. Total: 148,14 MWh. Entrada a 30 MW: **33,112 MWh**, não 60 MWh.

| Cenário corrigido | Energia de saída | Valor bruto indicativo | Emissões potencialmente deslocadas |
|---|---:|---:|---:|
| Baixo | 28,1452 MWh | R$ 1.649,31 | 6,03996 tCO₂ |
| Base | 29,8008 MWh | R$ 9.246,89 | 12,29184 tCO₂ |
| Alto | 29,8008 MWh | R$ 22.402,16 | 17,22486 tCO₂ |

O cálculo anterior de 51/54/54 MWh usava potência × duração total e superestimava a carga nas
janelas de pouco excedente. A correção não prova recuperação. Não somar cenários de episódios
como despacho da mesma bateria; faltam estado de carga e restrições compartilhadas.
Preço de venda/contrato, hora de descarga e custos reais não foram estimados. Carbono é uma
sensibilidade de deslocamento potencial, não efeito líquido: faltam contrafactual e emissões
adicionais. Se o cartão exigir impacto causal, deve mostrar “não estimado”.

### Validação e desconhecidos

Schema/unidades/metadados/datas/URLs/valores/eficiência são validados. Todos os três cenários são
obrigatórios; nulo deve ter `lacuna` explícita. Premissa de bateria nula produz energia nula em
`impact_sensitivity`, **não zero**. O contrato compartilhado ainda exige energia numérica:
`build_recommendations` recusa o caso indeterminado, cuja evolução foi proposta separadamente.
Zero nas outras ações significa apenas recuperação física não quantificada pela regra; não
significa ausência de direito financeiro. A UI precisa escrever isso e reter a orientação humana.

O resumo tático agora expõe `janelas_volume_valido`, `janelas_volume_nulo`,
`janelas_corte_indeterminado` e `energia_conhecida_mwh`. `energia_observada_mwh` é nula se
qualquer volume do grupo for desconhecido; grupo todo nulo também tem subtotal nulo. Não preencher
com zero na interface. Grupos táticos descrevem somente o período consultado, mesmo que a etiqueta
seja mês ou semana. O teste reservado segue proibido e caminhos legados não protegidos não podem
ser usados como atalho.
