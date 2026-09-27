# Roteiro do pitch do Zelo

Data: 27/09/2026. **Estado: aprovado pelo responsável.** A final é em 27/09, às 15h. O pitch
tem até 5 minutos, e este roteiro dura cerca de 3. Terminar antes do tempo é intencional,
como recomendou a mentoria.

Estrutura da mentoria: um dado de abertura e depois contexto, desejo, conflito, mudança e
resultado. Há uma dor só: **"o corte chega sem aviso"**.

Legenda:

- **[medido]**: calculado por nós;
- **[externo]**: referência de terceiros;
- **[cenário]**: exemplo retrospectivo com premissas declaradas.

## Frase de posicionamento

> Para as equipes que operam e mantêm usinas eólicas e solares, que hoje só descobrem o corte
> quando a ordem chega, o Zelo é um aviso diário de cortes que, toda noite, mostra em
> quais horas do dia seguinte cada usina deve ser cortada, por qual motivo e quanto esse aviso
> costuma acertar.

- **Analogia falada:** "é como a previsão do tempo, só que dos cortes".

## Blocos

| # | Bloco | Tempo | O que falar | Número | Tela |
|---|---|---|---|---|---|
| 0 | Dado de abertura | 20 s | "Em setembro, uma usina solar média no Brasil passou 7 das 12 horas de sol proibida de gerar tudo o que podia. Em 2025, esses cortes custaram cerca de R$ 6,5 bilhões." | 7,2 de 12,4 h **[medido]**; R$ 6,5 bi **[externo: Volt Robotics, citado no Caderno]** | O número "7 de 12 horas" |
| 1 | Contexto | 20 s | "Quando sobra energia ou a rede não aguenta, o operador do sistema manda as usinas eólicas e solares reduzirem a geração. Isso virou rotina." | Corte eólico de abril a agosto: 4,4 TWh (2024) → 12,2 TWh (2026) **[medido]** | Barras dos 3 anos |
| 2 | Desejo | 15 s | "As equipes que operam e mantêm essas usinas querem planejar o dia: quando parar uma máquina, como escalar o turno, quem avisar." | nenhum | Uma frase |
| 3 | Conflito | 20 s | "Mas a ordem chega sem aviso. A equipe só descobre na hora e passa o dia reagindo." | nenhum | "Sem aviso → só reage" |
| 4 | Mudança | 50 s | "O Zelo é um aviso diário de cortes. Toda noite, às 20h, mostra as horas de amanhã em que cada usina deve ser cortada, o motivo e quanto o aviso costuma acertar. Por trás, um modelo de inteligência artificial aprende o padrão de cada usina, usando só dados públicos do operador." | nenhum | **Vídeo pré-gravado do dashboard** (ver abaixo) |
| 5 | Prova | 25 s | "Testamos em setembro, com dados que o modelo nunca tinha visto. De cada 10 horas que avisamos, 8 tiveram corte. E 97% da energia cortada caiu em horas avisadas na noite anterior." | Precisão de 0,82 (eólica) e 0,81 (solar); 97,2% e 96,4% da energia **[medido]** | "8 em 10" e "97%" |
| 6 | Resultado | 30 s | "Com o aviso, a equipe decide antes. Por exemplo, remarca uma manutenção curta para as horas em que a usina já seria cortada. Em setembro, nas eólicas, essa parada teria perdido mais da metade menos energia do que uma parada marcada sem aviso." | **[cenário retrospectivo]** contra "8h às 10h" e "hora de menor geração" | Duas barras: sem aviso × remarcada |
| 7 | Fechamento | 20 s | "O corte não vai parar. O Zelo tira a surpresa. O próximo passo é um piloto com uma geradora, para medir o aviso na operação real." Depois, a equipe: nome e papel de cada um, em uma linha | nenhum | Frase de posicionamento e equipe |

## Fora do palco (só para perguntas)

- A comparação com o histórico da usina.
- A tentativa de prever o volume.
- O teste de clima perfeito.
- As horas livres. Elas aparecem na tela, mas não são faladas.
- A cobertura de 90–94% das meias-horas com corte. Ela repete o que o 97% já mostra.
- A lista longa de próximos passos.
- Respostas prontas: seção 7 de `docs/premissa-produto.md`.

## O que não dizer

- Que o Zelo evita o corte. O corte é uma ordem do operador do sistema.
- Que o operador do sistema não avisa ninguém. Não verificamos isso.
- Que só a IA consegue prever.
- Qualquer valor de economia anual.
- Jargão: "curtailment", "constrained-off", "AP", "recall".

## Vídeo do dashboard (bloco 4)

Os slides serão feitos no Canva e apresentados por link, que permite reproduzir vídeo. O plano
é gravar o dashboard mostrando o aviso de uma usina num dia de setembro.

Atualização de 27/09: o painel já foi reformulado sem volume e emite avisos ao vivo. O roteiro
do vídeo está no slide 06, abaixo. Se o vídeo não ficar pronto, a alternativa é uma imagem
estática do aviso real.

---

# Slides (estrutura para o Canva)

São 9 slides, com cerca de 3 minutos de fala. Os textos já estão prontos para colar; a
curadoria fina fica para depois. Números marcados como **[medido]**, **[externo]** ou
**[cenário]** levam a fonte num rodapé pequeno.

## Linha visual (a partir da referência "Volterra")

- **Slides claros:** fundo branco com um leve degradê azul-céu no canto superior direito.
- **Slides escuros:** fundo azul-marinho (`#0B1B3F`), com texto branco e cinza-azulado.
  - Os slides alternam entre claro e escuro, começando pelo escuro.
- **Paleta:**

  | Uso | Cor |
  |---|---|
  | Título | Azul-marinho `#0B1B3F` |
  | Destaque (segunda linha do título, números) | Azul vivo `#3B82F6` |
  | Detalhe (traço acima do título, pontos de conexão) | Amarelo `#FACC15` |
  | Cartões | Azul muito claro `#EEF4FF` |
  | Texto de apoio | Cinza `#64748B` |

- **Tipografia:** sans geométrica em negrito, como na referência. O título tem duas linhas: a
  primeira em marinho e a segunda em azul.
- **Elementos repetidos:**
  - logo Zelo no canto superior esquerdo;
  - contador "03 / 09" no canto superior direito;
  - traço amarelo curto acima do título.
- **Ícones:** de linha fina, dentro de círculos azul-claros.
- **Cartões:** cantos arredondados e borda sutil.
- **Número de destaque:** num cartão próprio, com rótulo em caixa alta e espaçado, como o "+32%"
  da referência.
- **Imagem:** foto de usinas eólicas e solares esmaecendo para o fundo, na lateral direita de
  alguns slides.
- **Painel no vídeo:** o painel tem visual próprio (papel e vermelho). No slide de demonstração,
  ele entra dentro de uma moldura de navegador, e o contraste vira intencional.

## Slide a slide

### 01 · Capa · escuro · 5 s

- **Título:** "Zelo" / (azul) "Aviso diário de cortes"
- **Subtítulo:** "Para usinas eólicas e solares saberem, na noite anterior, quando serão
  cortadas."
- **Visual:** foto de parque eólico e solar à direita, esmaecendo no marinho. Rodapé com
  "Hackathon IA COPPE 2026".
- **Fala:** nenhuma. O apresentador entra direto no slide 02.

### 02 · O dado · claro · 20 s

- **Número gigante, centralizado:** **7 de 12**
- **Legenda:** "horas de sol em que a usina solar média ficou cortada em setembro"
- **Visual:** 12 barras de hora, em fila. 7 delas ficam azuis, uma a uma, na animação.
- **Rodapé:** "Dados abertos do ONS, 01–24/09/2026 [medido]"
- **Fala:** "Em setembro, uma usina solar média no Brasil passou 7 das 12 horas de sol proibida
  de gerar tudo o que podia."

### 03 · Por que agora · escuro · 20 s

- **Título:** "O corte virou rotina." / (azul) "E continua crescendo."
- **Visual à esquerda:** três barras que crescem na animação.
  - 2024: **4,4 TWh**
  - 2025: **9,5 TWh**
  - 2026: **12,2 TWh**
  - Rótulo: "corte eólico de abril a agosto"
- **Cartão de destaque à direita:** "**R$ 6,5 bi**" / "CUSTO DO CORTE EM 2025"
- **Rodapé:** "ONS [medido] · Volt Robotics, citado no Caderno de Desafios [externo]"
- **Fala:** "Quando sobra energia ou a rede não aguenta, o operador do sistema manda as usinas
  reduzirem a geração. Isso deixou de ser exceção. Em 2025, custou cerca de 6,5 bilhões de
  reais."

### 04 · A dor · claro · 30 s

- **Título:** "Quem opera a usina quer planejar o dia." / (azul) "Mas o corte chega sem aviso."
- **Visual:** três cartões, no estilo da faixa inferior da referência.
  - Manutenção: "Quando parar uma máquina?"
  - Equipe: "Quem precisa estar de plantão?"
  - Comunicação: "Quem avisar, e quando?"
- **Frase abaixo dos cartões:** "Hoje, a equipe só descobre na hora e passa o dia reagindo."
- **Animação:** os cartões entram primeiro. A segunda linha do título entra depois da pausa.
- **Fala:** "As equipes que operam e mantêm essas usinas querem planejar o dia: quando parar uma
  máquina, como escalar o turno, quem avisar. Mas a ordem chega sem aviso."

### 05 · A solução · escuro · 30 s

- **Título:** "Zelo:" / (azul) "o aviso de amanhã, toda noite às 20h."
- **Visual:** diagrama em estrela, igual ao da referência.
  - **Entradas, à esquerda:**
    - "Dados públicos do ONS": restrições por usina, a cada meia hora;
    - "Histórico da usina": padrão das últimas semanas;
    - "Calendário": dia da semana e feriados.
  - **Centro:** nuvem "Zelo", com o ícone de raio.
  - **Saídas, à direita:**
    - "Quais horas": janelas de corte provável;
    - "Qual motivo": sobra de energia ou limite da rede;
    - "Quanto acerta": acerto medido, à vista.
- **Rodapé em destaque:** "Como a previsão do tempo, só que dos cortes de energia."
- **Fala:** "O Zelo é um aviso diário de cortes. Toda noite, às 20h, ele mostra em quais
  horas do dia seguinte cada usina deve ser cortada, por qual motivo e quanto esse aviso costuma
  acertar. Um modelo de inteligência artificial aprende o padrão de cada usina, usando só dados
  públicos."

### 06 · Em funcionamento · claro · 35 s

- **Título pequeno:** "O aviso na prática"
- **Visual:** o vídeo ocupa cerca de 70% do slide, dentro de uma moldura de navegador. À direita,
  três passos numerados, que acendem conforme o vídeo avança:
  1. **"Amanhã, segunda-feira"**: o aviso emitido às 20h da véspera;
  2. **"O portfólio num olhar"**: vermelho é hora em alerta, verde é hora livre;
  3. **"O aviso de cada usina"**: janela, motivo e sugestão.
- **Roteiro do vídeo** (cerca de 30 s, sem som):
  1. topo do painel com "Amanhã…";
  2. filtrar só solar;
  3. rolar até o mapa;
  4. clicar na primeira usina da tabela;
  5. parar no aviso (janela, motivo) e nas horas livres.
  - Grave depois das 20h de hoje, para o título dizer "Amanhã, segunda-feira, 28 de setembro".
- **Rodapé:** "Avisos reais, emitidos às 20h da véspera com dados do ONS"
- **Fala:** "Esta é a tela que a equipe abre na noite anterior. De relance, o portfólio: vermelho
  é hora com corte provável, verde é hora livre. Numa usina solar, por exemplo: corte provável
  no meio do dia, por sobra de energia no sistema. As horas livres ficam à vista."

### 07 · Quanto acerta · escuro · 25 s

- **Título:** "Testado com dados" / (azul) "que o modelo nunca viu."
- **Visual:** dois cartões grandes, lado a lado, no estilo do "+32%".
  - "**8 em 10**" / "HORAS AVISADAS TIVERAM CORTE"
  - "**97%**" / "DA ENERGIA CORTADA CAIU EM HORAS AVISADAS"
- **Rodapé:** "Setembro/2026, fora da amostra; unidade: usina × meia-hora [medido]"
- **Fala:** "Testamos em setembro, com dados que o modelo nunca tinha visto. De cada 10 horas que
  avisamos, 8 tiveram corte. E 97% da energia cortada caiu em horas avisadas na noite anterior."

### 08 · O que muda · claro · 30 s

- **Título:** "Com o aviso," / (azul) "a equipe decide antes."
- **Visual:** duas barras horizontais de "energia perdida numa parada de 2 h".
  - "Parada marcada sem aviso": barra longa, em cinza.
  - "Parada remarcada para as horas avisadas": barra com menos da metade do comprimento, em
    azul.
  - Cartão de destaque: "**−50%+**" / "ENERGIA PERDIDA NA PARADA · EÓLICAS"
- **Rodapé:** "Cenário retrospectivo, set/2026, parada de 2 h; comparado com 'das 8h às 10h' e
  com 'a hora de menor geração' [cenário]"
- **Fala:** "Por exemplo: remarcar uma manutenção curta para as horas em que a usina já seria
  cortada. Em setembro, nas eólicas, essa parada teria perdido mais da metade menos energia do
  que uma parada marcada sem o aviso."

### 09 · Fechamento · escuro · 25 s

- **Título:** "O corte não vai parar." / (azul) "O Zelo tira a surpresa."
- **Faixa do meio:**
  - frase de posicionamento em tamanho menor;
  - selo "no ar: aviso emitido todo dia às 20h".
- **Próximo passo:** um cartão com "Piloto com uma geradora: medir o aviso na operação real".
- **Equipe:** uma fila de cartões com foto, nome e papel. *(Pendente: nomes e papéis.)*
- **Fala:** "O corte não vai parar. O Zelo tira a surpresa. Nosso próximo passo é um piloto
  com uma geradora, para medir o aviso na operação real. Somos [equipe]."
