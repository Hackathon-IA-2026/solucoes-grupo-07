# Pivô: agenda de manutenção flexível solar, com radar e contexto de causa

## Decisão de produto

O cliente inicial é a equipe de operação/manutenção de uma geradora solar. A pergunta
entregável passa a ser: **“Tenho uma intervenção flexível de duas horas amanhã: qual
janela merece avaliação e quanto essa escolha teria custado em casos passados?”**

O CurtaMap prevê **quando há maior probabilidade de corte** e apresenta a **distribuição
histórica das causas já publicadas**. A causa não é inferida pelo modelo de ocorrência.
O painel sugere uma janela para discussão com a operação, permite confrontá-la com
referências simples e exibe a conferência retrospectiva em reais. Não prevê MWh cortados.

**Recomendação:** piloto supervisionado solar. Manter eólica como radar, sem adotar a
regra de manutenção baseada somente em alerta: ela perde para a menor geração histórica.
Nenhuma receita foi promovida ao preditor padrão nem implantada em produção.

## O que foi medido

Protocolo registrado antes da análise financeira em [protocolo.md](protocolo.md).
Agosto/2026 já foi examinado no projeto: toda esta avaliação é retrospectiva de
desenvolvimento, **não teste cego novo**. Dados ONS locais conferem com os hashes da
auditoria anterior. O CSV oficial CCEE foi baixado pela interface pública em 26/09/2026,
após bloqueio das chamadas de terminal, e identifica o PLD horário por submercado.

O classificador é exatamente o HGB de ocorrência já servido na v1/v3: 14 features,
300 iterações, semente 0, treino de 365 dias, rótulos até 30/07/2026. Os limiares são
os congelados com janeiro–abril: 0,3025 eólica e 0,3235 solar. Não foram ajustados em agosto.
Só foram retidas menos colunas na construção das features para caber na memória.

| Fonte | Linhas avaliadas | AP HGB | AP histórico 28d | Brier HGB | Precisão | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Eólica | 227.660 | 0,9210 | 0,9032 | 0,0942 | 81,69% | 94,54% | 0,8765 |
| Solar | 121.200 | 0,9077 | 0,8664 | 0,0651 | 79,59% | 91,60% | 0,8517 |

AP e Brier reproduziram os valores anteriores **sem diferença numérica** nas duas fontes.
Isso confirma a reprodução, não uma melhoria nova da IA. [paridade.csv](paridade.csv)
contém a conferência; [metricas_ocorrencia.csv](metricas_ocorrencia.csv) contém baselines,
TP/FP/FN/TN, cobertura, nulos e recortes por idade da informação. “Mesmo dia anterior”
não está publicado às 20h; a referência temporal usa o último dia efetivamente liberado.

## Como ligar o “quando” a reais sem prever volume

Supomos uma intervenção de **2h**, deslocável dentro de **08h–18h**, afetando **10% da
geração da entidade ONS**. Essas condições são premissas, não ordens de serviço reais.
Cada estratégia escolhe o horário com a informação disponível na emissão:

1. CurtaMap: maior média de P(corte) nas quatro meias-horas consecutivas.
2. Fixo: 08h–10h, referência ilustrativa; não é agenda observada de um cliente.
3. Histórico de corte: maior frequência histórica em 28 dias, no mesmo formato de bloco.
4. Menor geração histórica: menor geração média por horário nos 28 dias já publicados.

Empates escolhem o horário mais cedo. PLD, geração e causa realizados do dia-alvo
**não participam da escolha**. O custo é pontuado depois:

`custo de oportunidade = Σ geração observada [MW] × 0,5 [h] × fração parada × PLD [R$/MWh]`

`diferença = custo da referência − custo CurtaMap`

Diferença positiva significa custo contrafactual menor; negativa significa piora.
O PLD é referência de valoração, não receita contratada. Essa conta não calcula
ressarcimento, ESS, lucros, ganho de bateria ou economia realizada.

### Resultado a PLD horário observado, fração 10%

| Fonte | Comparação | Diferença média por oportunidade | Mediana | Melhores / piores / empates |
|---|---|---:|---:|---:|
| Solar | vs. 08h–10h | **+R$ 265,43** | +R$ 7,28 | 1.363 / 1.073 / 89 |
| Solar | vs. frequência histórica de corte | +R$ 49,41 | R$ 0,00 | 683 / 464 / 1.378 |
| Solar | vs. menor geração histórica | **+R$ 244,14** | +R$ 19,41 | 1.338 / 1.103 / 84 |
| Eólica | vs. 08h–10h | +R$ 314,94 | +R$ 94,45 | 3.812 / 660 / 269 |
| Eólica | vs. frequência histórica de corte | +R$ 26,52 | R$ 0,00 | 1.129 / 548 / 3.064 |
| Eólica | vs. menor geração histórica | **−R$ 75,40** | −R$ 1,23 | 1.500 / 2.574 / 667 |

São **2.525 oportunidades solares**, todas avaliáveis, e **4.743 eólicas**, com 4.741
avaliáveis nas quatro estratégias. Nulos não viram zero. Os valores foram comparados
na mesma amostra. Uma oportunidade é uma usina/dia alternativa: não se presume que
todas as usinas parem todos os dias. **A soma das oportunidades não é economia mensal.**

A solar melhora em 53,0% dos casos contra menor geração histórica e piora em 43,7%.
A média muito superior à mediana indica concentração do valor em poucos casos maiores.
Na agregação semanal, a solar teve diferença média positiva em 5 de 6 blocos, incluindo
duas semanas parciais; a semana de 24/08 foi negativa (−R$ 13,25 por oportunidade).
A eólica perdeu para menor geração histórica nos seis blocos. Não há demonstração
de estabilidade entre meses neste estudo financeiro.

Os resultados completos, inclusive sensibilidades a preços fixos de **R$ 50, 100 e
200/MWh** (cenários, não PLD observado), estão em [impacto_manutencao.csv](impacto_manutencao.csv)
e [impacto_semanas.csv](impacto_semanas.csv). A UI também varia a fração parada de 1% a 100%.
O efeito dessa fração é estritamente linear na simulação; não é um modelo físico da usina.

## Papel da causa e das fontes externas

- **ONS:** gerações e registros de restrição sustentam o replay, a conferência posterior e
  a distribuição de causa das ordens dos últimos 28 dias publicados. Contam-se registros
  de meia-hora, não eventos independentes. O contexto tem corte temporal e tamanho da amostra.
  [Catálogo eólico](https://dados.ons.org.br/dataset/restricao_coff_eolica_usi).
- **CCEE:** o [PLD horário oficial](https://dadosabertos.ccee.org.br/dataset/pld_horario)
  fornece preço por hora/submercado em R$/MWh. O
  [dicionário](https://dadosabertos.ccee.org.br/dataset/pld_horario/resource/3f279d6b-1069-42f7-9b0a-217b084729c4)
  e o CSV foram conferidos. `HORA` é 0–23; as duas meias-horas recebem o mesmo preço.
  A revisão atual é usada só para pontuação posterior, sem alegar disponibilidade histórica às 20h.
  Dados CC-BY-4.0; crédito CCEE; transformações: normalização e junção temporal.
- **EPE:** as [ferramentas interativas](https://epe.gov.br/pt/publicacoes-dados-abertos/ferramentas-interativas)
  são úteis para contexto de oferta e expansão. Não fornecem nesta análise a agenda real
  de manutenção nem o contrato financeiro de cada gerador. Não acrescentar dados apenas
  para citar mais instituições; ficaram como apoio ao dimensionamento de mercado futuro.
- **INPE:** a [base SONDA](https://sonda.ccst.inpe.br/sobre_base.html) é observacional.
  A página informa que só os dados solarimétricos estão sendo disponibilizados no momento.
  Não tratamos observação ou estimativa histórica como previsão disponível na emissão.
  Previsões arquivadas e condições meteorológicas de segurança são evolução, não requisito
  para esta demonstração. Nenhum ganho foi atribuído à EPE ou ao INPE nesta execução.

Reaproveitamos a separação entre ocorrência e causa do produto e a cautela das regras
de recomendação da equipe. Não importamos o código da branch de recomendação ou interface:
o trabalho está isolado e o painel é uma entrada explícita para revisão.

## O que mostrar no pitch

“O CurtaMap ajuda a discutir **quando fazer uma intervenção flexível que já seria
necessária**. A IA sinaliza os horários de corte; a causa vem do histórico oficial.
Em uma simulação retrospectiva solar de agosto, com parada de 2h e 10% da geração
afetada, os horários escolhidos tiveram custo médio **R$ 244 menor por oportunidade**
que uma regra de menor geração histórica, a PLD observado. Houve perdas em 44% dos
casos. O próximo passo é validar a decisão na agenda real de um gerador.”

Mostrar um dia escolhido pelo usuário, as 48 probabilidades, a amostra de causas, o
horário proposto e o custo comparado. Alternar para um caso com diferença negativa.
Não usar a melhor usina isolada como resultado representativo nem multiplicar a média
pelo parque nacional para anunciar mercado ou retorno.

## Limitações e confirmação futura

- Manutenção real pode ser indivisível, já agendada, exigir equipe, clima seguro,
  autorização e antecedência maior que D+1. A tela não autoriza despacho ou intervenção.
- Geração observada sem a nova parada não identifica o efeito causal da parada. A
  redistribuição do corte entre equipamentos/usinas pode mudar o resultado. A fração
  proporcional de geração sacrificada é uma hipótese operacional, não evidência física.
- Entidades ONS podem ser conjuntos; não são necessariamente um único ativo ou contrato.
- Não incluímos mão de obra, mobilização, manutenção noturna, penalidades, contratos,
  compensações ou efeito em outros dias. Se manutenção noturna for viável, é necessário
  acrescentar essa referência, especialmente na solar.
- Um mês, sem ensaio prospectivo; usinas/dias são correlacionados. Não há teste de
  significância ou inferência causal. Setembro já foi usado anteriormente.
- Confirmar com agenda real, fração tecnicamente desligável e regras de contratação;
  congelar a política e medir custo por intervenção em dias ainda não observados.
  Adotar só se superar a prática real do cliente, incluindo custos adicionais.

## Execução local e arquivos

Leia [COMO-RODAR.md](COMO-RODAR.md). Código: `curtamap.previsao.alertas`,
`curtamap.alertas_negocio` e `curtamap.alertas_app`. Dados individuais, modelos e CSV
CCEE permanecem ignorados pelo Git. [manifesto.json](manifesto.json) registra hashes,
versões, períodos, features, parâmetros, limiares, memória e tempo.

O piloto solar de custo (30 dias de treino, uma semana prevista) levou 9s e 0,77 GiB
privados. Na reprodução final: solar 34s de processamento (1,53 GiB privados amostrados),
eólica 70s (2,82 GiB), duas threads. A tentativa eólica anterior foi interrompida a 3 GiB;
a projeção de colunas resolveu sem mudar AP/Brier. RAM total 15,89 GiB, CPU Ryzen 5 4600G;
GPU não utilizada. A leitura de dados e o monitor têm custos incluídos no tempo de parede
maior registrado nos manifestos. Nenhum serviço pago ou deploy.

Validação final: **256 testes passaram, 1 pulado** (reexecução da EDA sem Parquet no
`data/raw` deste worktree). `ruff check .` e `ruff format --check .` passaram. O painel
foi conferido no navegador com dados reais e com resultado financeiro negativo visível.
