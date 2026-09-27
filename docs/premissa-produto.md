# Premissa do produto Zelo

Data: 27/09/2026. **Estado: fechada em 27/09 pelo responsável; o roteiro do palco está em `docs/roteiro-pitch.md`.** Depende do
posicionamento decidido em `docs/posicionamento-pitch.md` (P1 com a cena do P2) e dos números
de `docs/reports/pitch-impacto/README.md`.

Legenda dos números:

- **[medido]**: calculado por nós, com a fonte citada;
- **[externo]**: referência de terceiros;
- **[cenário]**: premissas declaradas, e não resultado;
- **[hipótese]**: ainda sem evidência.

---

## 1. A frase de posicionamento

> **Para** as equipes que operam e mantêm usinas eólicas e solares, **que** hoje só descobrem
> o corte quando a ordem chega, **o Zelo é** um aviso diário de cortes **que**, toda noite,
> mostra em quais horas do dia seguinte cada usina deve ser cortada, por qual motivo e quanto
> esse aviso costuma acertar.

**Teste de repetição:** quem ouvir deve conseguir dizer "é uma previsão do tempo, só que dos
cortes de energia, para a usina se preparar".

## 2. Persona, momento e gatilho

- **Quem:** a equipe que opera uma ou várias usinas eólicas ou solares. Na prática, a sala de
  operação e quem planeja o dia seguinte (manutenção, turno, comunicação interna)
  **[hipótese]**. Não conversamos com operadores reais.
- **Quando:** às 20h, na noite anterior. É a hora em que o Zelo emite o aviso, com os
  dados que o ONS já publicou. O uso de fato acontece na manhã seguinte, no planejamento do
  dia.
- **Qual é a dor, em uma frase:** "o corte chega sem aviso, e a gente só reage".
- **Por que a dor é grande agora:**
  - Em setembro de 2026, uma usina solar média ficou cortada em **7,2 das 12,4 horas com
    sol**, e uma eólica média em **11,7 horas por dia** **[medido]**.
  - O corte eólico de abril a agosto foi de 4,4 TWh (2024) para 12,2 TWh (2026) **[medido]**.
  - O corte custou cerca de **R$ 6,5 bilhões** em 2025 **[externo: Volt Robotics, citado no
    Caderno]**.

## 3. O que o produto entrega

O "aviso das 20h" tem uma linha por usina, para o dia seguinte:

1. **Horas em alerta.** As meias-horas com chance alta de corte, agrupadas em janelas
   legíveis, como "11h às 15h".
   - Cada janela traz a chance de corte e o limiar que separa alerta de não alerta.
   - Hoje o produto emite por meia-hora. **O agrupamento em janelas ainda não existe** e é
     trabalho de interface.
2. **Horas livres.** O complemento das janelas: quando a usina deve gerar normalmente. Com o
   corte virando rotina, essa informação vale tanto quanto a do corte.
3. **Motivo típico**, com a origem visível. Por exemplo: "nas últimas 4 semanas, a maioria
   das ordens nesta usina neste horário foi por *sobra de energia no sistema*". A alternativa
   é *limite da rede*.
   - Os códigos oficiais `ENE`, `CNF` e `REL` são traduzidos conforme o Caderno.
4. **Quanto o aviso acerta.** Em setembro, fora da amostra:
   - "de cada 10 horas avisadas, 8 tiveram corte" **[medido]**;
   - "quase toda a energia cortada (96–97%) caiu em horas avisadas" **[medido]**.
5. **Visão de portfólio.** As usinas ordenadas pelas horas em alerta amanhã, para quem cuida
   de várias.

**O que o aviso não diz** (e a tela deve dizer que não diz):

- quantos MWh serão cortados;
- quanto isso custa;
- se a ordem será obedecida ou revista pelo ONS.

## 4. Decisões que o aviso apoia (exemplos, não lista fechada)

| Decisão | Como o aviso muda | Evidência |
|---|---|---|
| **Manutenção flexível** (a cena do pitch) | Remarcar a parada para as horas em que a usina já seria cortada | **[cenário]** Em setembro, uma parada de 2 h remarcada para as horas avisadas perdeu **mais de 50% menos energia** na eólica e **20–30% menos** na solar, contra "8h às 10h" ou "hora de menor geração" |
| Comunicação interna | A operação avisa o comercial e a gestão na véspera, e não depois | **[hipótese]** |
| Escala da equipe | Turno preparado para receber e cumprir ordens nas janelas | **[hipótese]** |
| Conferência posterior | O esperado fica registrado para comparar com o que o ONS publicar | **[hipótese]**. Regras de ressarcimento não verificadas |
| Atenção no portfólio | Priorizar as usinas com mais horas em alerta | **[hipótese]** |

**O dinheiro no palco (formato decidido: c).**

- O pitch liga o produto ao tamanho da perda **sem prometer recuperá-la**:
  > "O corte custou cerca de R$ 6,5 bilhões em 2025. Quase toda essa perda acontece em horas
  > que o Zelo avisa na noite anterior."
- A cena da manutenção mostra que o aviso vira decisão.
- Nenhum valor de economia anual é anunciado.

## 5. Onde está a IA e onde está a regra

- **Modelo de IA:** a chance de corte por usina e meia-hora para o dia seguinte.
  - Ele aprende o padrão de cada usina e o ajusta ao momento: se a região está cortando mais
    ou menos agora, o dia da semana, feriados e a idade da informação disponível.
  - Acerta mais que o histórico da própria usina em todos os meses testados **[medido]**.
- **Regra transparente:** o motivo típico. Ela é simples de propósito, porque ninguém
  precisa confiar numa caixa-preta para entender por que a usina é cortada.
- **Diferencial:** o aviso chega pronto, por usina e por hora, com motivo e índice de acerto
  à vista. A precisão sustenta o produto, mas não é o que ele vende.

## 6. De onde viemos e para onde vamos

**A história de evolução**, para contar em uma frase no pitch:

> "Tentamos também prever **quanto** seria cortado. Na solar funcionou, mas na eólica o erro
> ainda era alto demais para uma decisão. Preferimos entregar só o que é confiável, e já
> sabemos o que falta."

Fatos que a sustentam **[medido]**:

- **Volume solar:** o modelo venceu o histórico (erro WAPE de 0,607 contra 0,652 em
  setembro).
- **Volume eólico:** empate técnico com o histórico. Nenhuma das 6 variantes testadas na v2 passou da
  regra acima do ruído. As faixas de volume
  ajudaram só em recortes.
- **Motivo previsto por modelo:** não superou a regra do histórico. Por isso servimos a
  regra.
- **Teste de clima perfeito** (teto, não produto): se soubéssemos o vento e o sol do dia
  seguinte, o acerto eólico subiria de AP 0,826 para 0,872, e o erro diário do volume eólico
  cairia cerca de 24% (médias de mai–ago).
  - **A próxima alavanca é a previsão meteorológica**, e não um modelo mais complexo.

Próximos passos, em ordem de valor:

1. **Piloto com uma geradora ou transmissora** (critério de viabilidade da banca). Validar
   com a operação real quais decisões o aviso muda e medir o efeito nas próprias decisões
   dela.
2. **Previsão meteorológica** como entrada. É o maior ganho medido (teto do teste de clima)
   e reabre o volume.
3. **Quanto será cortado.** Voltar ao volume com clima. A solar já está pronta para um
   primeiro teste.
4. **Entrega onde a equipe já trabalha.** O aviso por e-mail, mensagem ou API, integrável a
   outros sistemas (a ideia de MCP citada na mentoria).
   - **Não existe hoje.**
5. **Resumo em linguagem natural.** Um LLM que só verbaliza os números já calculados, com
   texto padrão se falhar (`docs/architecture.md`).
   - **Não existe hoje.**
6. **Recalibração periódica** e acompanhamento do acerto ao longo do tempo, com o índice
   exibido na própria tela.

## 7. Perguntas de bolso (não entram no pitch, mas precisam de resposta pronta)

| Pergunta provável | Resposta |
|---|---|
| "O ONS já não faz isso?" | O ONS opera o sistema e publica o corte depois. Não entrega ao gerador um aviso por usina na noite anterior |
| "Se eu olhar o histórico da usina, não consigo o mesmo?" | O histórico é o nosso ponto de partida. O modelo o supera em todos os meses, e o Zelo entrega isso pronto, todo dia, com motivo e índice de acerto |
| "Vocês evitam o corte?" | Não. O corte é uma decisão do operador do sistema. O Zelo tira a surpresa, para a usina se preparar |
| "Quanto o gerador economiza?" | Depende da decisão. No exemplo da manutenção, a parada remarcada perdeu mais da metade menos energia na eólica em setembro. Não anunciamos um total anual porque não conhecemos a agenda real de cada gerador |
| "E sem previsão do tempo?" | Hoje o aviso usa só dados já publicados. Medimos que o clima é a próxima alavanca |
| "Por que o motivo não é previsto por IA?" | Testamos, e a regra do histórico acertou mais. Preferimos o que é melhor e explicável |

## 8. Decisões de 27/09

- **Persona do palco:** as equipes que operam e mantêm a usina. A geradora dona do portfólio
  é quem paga e aparece só se perguntarem **[hipótese]**.
- **Categoria:** "aviso diário de cortes". "Como a previsão do tempo, só que dos cortes" é a
  analogia falada, e não a categoria.
- **"Com inteligência artificial" saiu da frase.** O diferencial é o aviso pronto, com motivo
  e acerto à vista. A IA aparece no bloco da solução.
- **Horas livres:** detalhe da tela, fora da promessa.
- **Dinheiro em duas frases**, sem estender a 2025 a cobertura medida em setembro:
  - "O corte custou cerca de R$ 6,5 bilhões em 2025" **[externo]**;
  - "Em setembro, 97% da energia cortada caiu em horas avisadas na véspera" **[medido]**.
- **Pitch enxuto:** a história da tentativa de prever o volume (seção 6) e o teste de clima
  ficam fora do palco. Servem só para responder perguntas.
- **Demonstração:** vídeo pré-gravado do dashboard, depois da reformulação sem volume.
