# Regras de recomendação e cenários de impacto — versão 1

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
causa nula ou mudança de causa, `causa_base` fica nula: o CurtaMap não elege uma causa dominante.
Isso é conservador porque o próprio ONS registra que a classificação pode mudar ao longo do dia.

## Matriz causa → ação

| Causa | Ação determinística | Antecedência e diferença por fonte | Limite operacional/regulatório | Natureza |
|---|---|---|---|---|
| REL | `PRESERVAR_EVIDENCIAS_ESS`: confirmar mensagem, preservar telemetria e preparar conferência da apuração | Assim que o alerta surgir. Eólica: conferir vento e curva de produtividade. Solar: conferir irradiância e função de produtividade, especialmente em horas de sol | Não elevar geração contra o limite. ONS calcula referência final para REL; eventual ESS depende da apuração e das regras vigentes, não da previsão | Fato regulatório para a apuração; utilidade antecipatória é hipótese de produto |
| CNF | `COORDENAR_OPERACAO`: alinhar centro de operação e, se possível, deslocar manutenção flexível | Assim que o alerta surgir; revalidar a cada mensagem. Em solar, a janela útil termina com a irradiância; em eólica, o recurso pode persistir à noite | Segurança elétrica prevalece. Não há recuperação autônoma nem receita pressuposta | Limite é fato ONS; deslocar manutenção é hipótese a validar com o gerador |
| ENE | `AVALIAR_ARMAZENAMENTO`: simular carga de bateria e descarga posterior | Antes de `inicio`, usando a antecedência exibida. Solar tende a concentrar oportunidade diurna; eólica pode incluir noite | Só vale com bateria instalada/habilitada, potência, capacidade e estado de carga disponíveis, conexão e comando compatíveis. A descarga futura também precisa ser possível | Existência de armazenamento como flexibilidade é fato setorial; uso atrás desta recomendação é cenário |
| PAR | `REVISAR_PARECER_ACESSO`: conferir limite e priorizar estudo de conexão/reforço | No planejamento e antes da janela; não é correção em tempo real | A limitação consta do parecer de acesso. O cenário de recuperação imediata é zero até existir solução aprovada | Definição é fato ONS; escolha de priorização é decisão de produto |
| nula/desconhecida | `VALIDAR_CAUSA`: confirmar a mensagem do ONS antes de qualquer resposta específica | Imediatamente, mostrando explicitamente “causa indeterminada” | Proibido inferir causa pelo volume, fonte ou origem | Decisão conservadora do CurtaMap |

Para REL, a [REN ANEEL nº 1.030/2022](https://www2.aneel.gov.br/cedoc/ren20221030.html) e o
procedimento do ONS delimitam o tratamento do constrained-off e da apuração. A NT do ONS informa
que, para pagamento de ESS pela CCEE, a geração de referência final é calculada para eventos REL.
Logo, o CurtaMap nunca aplica PLD diretamente para afirmar ressarcimento.

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
O CurtaMap também não garante que a causa continuará ENE, que haverá espaço para descarga futura
ou que esse conjunto do ONS corresponda a uma única usina física. O valor para o pitch é mostrar
a passagem rastreável de previsão → regra → premissa → cenário → limite, sem transformar hipótese
em promessa.

## Resumo tático observado

`summarize_history` chama `derive_targets` e agrega dados reais por fonte, entidade, semana/mês,
causa, UF e subsistema. As saídas são `janelas_observadas`, `janelas_com_corte` e
`energia_observada_mwh`; não são previsão. A função recusa qualquer linha com
`din_instante >= 2026-05-01` enquanto o teste reservado estiver protegido.

