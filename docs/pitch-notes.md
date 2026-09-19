# Evidências e notas para a apresentação

Este arquivo preserva material de negócio ao longo do desenvolvimento. Atualize-o quando uma decisão, experimento ou descoberta puder sustentar o pitch final.

## Estrutura narrativa

1. **Problema:** qual perda concreta o gerador enfrenta e como ela aparece nos dados?
2. **Por que agora:** o que mudou em escala, dados, regulação ou tecnologia?
3. **Solução:** como o CurtaMap transforma antecipação em decisão?
4. **Papel da IA:** onde ela é indispensável e onde usamos regras determinísticas?
5. **Impacto:** quais MWh, reais e emissões podem ser afetados, sob quais premissas?
6. **Credibilidade:** quais resultados, limitações e capacidades da equipe sustentam a proposta?

## Evidências atuais

Legenda de estado:

- **Reproduzido no snapshot:** calculado por nós no notebook
  `notebooks/01_eda_fundamentos_dados.ipynb`, com `assert` na seção 13.
- **Validado contra publicação atual:** confrontado com os Parquet atuais do ONS
  (`docs/reports/stage1/official-comparison.json`).
- **Referência externa:** número de terceiros, não reproduzido por nós.
- **Hipótese:** interpretação plausível ainda sem evidência direta.

Todo volume é a GNR analítica (`max(referência − geração, 0)` quando há limitação) em MWh,
uma **estimativa provisória**. Não é ressarcimento, liquidação CCEE nem valor financeiro.

### Problema

| Afirmação | Estado | Evidência |
|---|---|---|
| Em 2025, eólica + solar deixaram de gerar cerca de **37,2 TWh** segundo a GNR analítica (70% eólica) | Reproduzido no snapshot; validado contra publicação atual (−0,016% eólica, −0,021% solar em 2025) | Notebook, seções 5 e 12; `target-definition.md` |
| 18% (eólica) e 22% (solar) das ordens de limitação têm volume zero: **comando ≠ corte** | Reproduzido no snapshot | Notebook, seção 2 |
| Cortes vêm em **episódios longos**: mediana de 4,5–5 h; só 15–16% duram 30 min | Reproduzido no snapshot | Notebook, seção 8 |
| O corte é **geograficamente concentrado**: RN 32%, BA 29%, MG 13%; NE 84% (2025) | Reproduzido no snapshot | Notebook, seção 5 |
| 36 de 180 entidades eólicas e 13 de 87 solares respondem por 50% da energia | Reproduzido no snapshot | Notebook, seção 6. Entidades são conjuntos, **não usinas físicas** |
| Cerca de 20% da geração potencial eólica e solar foi cortada em 2025 | Referência externa (Caderno, citando Volt Robotics) | Não reproduzido: o denominador “potencial” não é o mesmo que o nosso |
| 4.021 MWmed médios e cerca de R$ 6,5 bilhões em 2025 | Referência externa (Caderno) | Não reproduzido. Nosso total equivale a cerca de 4.248 MWmed, mas a proximidade não valida o número externo; o valor financeiro não foi calculado |

### Por que agora

| Afirmação | Estado | Evidência |
|---|---|---|
| Na mesma janela abr–ago, o corte eólico foi de 4,40 TWh (2024) para 9,54 (2025) e 12,24 TWh (2026) | Reproduzido no snapshot | Notebook, seção 3 |
| O crescimento eólico não é só a entrada de novas usinas: o painel fixo de 135 entidades vai de 3,18 para 7,61 e 10,27 TWh | Reproduzido no snapshot | Notebook, seção 11 |
| O crescimento **solar** de 2025 para 2026 vem de entidades novas: o painel fixo de 50 entidades fica estável (3,39 → 3,36 TWh) | Reproduzido no snapshot | Notebook, seção 11. **Não dizer que “o corte solar por usina segue crescendo em 2026”** |
| A causa mudou: CNF dominava a eólica em 2024 (61%); ENE domina em 2025 (51%) e 2026 (61%). Na solar, ENE chega a 84% em 2026 | Reproduzido no snapshot | Notebook, seção 4 |
| ENE eólico, na janela abr–ago, foi de 0,75 para 5,61 e 7,96 TWh; CNF ficou em cerca de 3 TWh | Reproduzido no snapshot | Notebook, tabela 5 |
| O crescimento de ENE reflete a expansão renovável e o excedente no meio do dia | Hipótese | Os dados não medem a causa física |

### Solução e papel da IA

| Afirmação | Estado | Evidência |
|---|---|---|
| Há sinal para antecipar: P(corte \| corte 24 h antes) = 70% eólica e 71% solar, contra bases de 26% e 19% | Reproduzido no snapshot (descritivo) | Notebook, seção 8. **Não é acurácia de modelo** |
| Como a persistência é alta, baselines ingênuos serão fortes; o modelo precisa superá-los | Interpretação | Etapa 2 medirá isso |
| Causas diferentes exigem respostas diferentes | Tese de produto, apoiada na taxonomia ONS | Causas e origens estão rotuladas em ~100% das limitações (42 lacunas solares) |

### Credibilidade e limitações a assumir publicamente

- A fórmula reproduz 3.127.621 GNRa publicadas pelo ONS, sem divergência acima de 0,001 MW
  (validado contra publicação atual).
- O ONS revisa os dados: 47 de 64 meses do snapshot diferem da publicação atual, e há meses de
  2023 regravados em setembro de 2026. Os totais são provisórios.
- O timestamp não tem fuso nem convenção de início/fim; perfis horários valem “como publicados”.
- Vento e irradiância disponíveis são **verificados**, não previsão: não servem como feature D+1.
- A latência de publicação dos dados ONS é desconhecida e pode limitar o uso do histórico recente.

## Requisitos narrativos recuperados da reunião de tira-dúvidas

- Fundamentar o problema com dados e fontes.
- Defender a solução e sua urgência: “por que agora?”.
- Explicar vantagens, limitações e evolução das tecnologias.
- Evidenciar se a IA é central ou ferramenta de apoio.
- Mostrar capacidade da equipe e recursos necessários além do protótipo.

## Registro de decisões

Para cada decisão relevante, anote:

- data e contexto;
- alternativas consideradas;
- evidência observada;
- decisão e motivo;
- impacto esperado no usuário;
- limitação ou hipótese ainda aberta;
- gráfico, métrica ou demonstração que pode representá-la no palco.

## Resultados a preencher

- Cobertura e qualidade dos rótulos: **preenchido** (seção 9 do notebook).
- Concentração do curtailment por entidade e causa: **preenchido** (seções 4 e 6).
- Baselines e melhoria dos modelos: Etapa 2.
- Exemplo de recomendação rastreável: Etapa 3.
- Cenários de impacto e sensibilidade: Etapa 3.
- Limitações assumidas publicamente: ver a seção de credibilidade acima; revisar a cada etapa.
