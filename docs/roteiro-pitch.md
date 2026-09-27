# Roteiro do pitch do CurtaMap

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
> quando a ordem chega, o CurtaMap é um aviso diário de cortes que, toda noite, mostra em
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
| 4 | Mudança | 50 s | "O CurtaMap é um aviso diário de cortes. Toda noite, às 20h, mostra as horas de amanhã em que cada usina deve ser cortada, o motivo e quanto o aviso costuma acertar. Por trás, um modelo de inteligência artificial aprende o padrão de cada usina, usando só dados públicos do operador." | nenhum | **Vídeo pré-gravado do dashboard** (ver abaixo) |
| 5 | Prova | 25 s | "Testamos em setembro, com dados que o modelo nunca tinha visto. De cada 10 horas que avisamos, 8 tiveram corte. E 97% da energia cortada caiu em horas avisadas na noite anterior." | Precisão de 0,82 (eólica) e 0,81 (solar); 97,2% e 96,4% da energia **[medido]** | "8 em 10" e "97%" |
| 6 | Resultado | 30 s | "Com o aviso, a equipe decide antes. Por exemplo, remarca uma manutenção curta para as horas em que a usina já seria cortada. Em setembro, nas eólicas, essa parada teria perdido mais da metade menos energia do que uma parada marcada sem aviso." | **[cenário retrospectivo]** contra "8h às 10h" e "hora de menor geração" | Duas barras: sem aviso × remarcada |
| 7 | Fechamento | 20 s | "O corte não vai parar. O CurtaMap tira a surpresa. O próximo passo é um piloto com uma geradora, para medir o aviso na operação real." Depois, a equipe: nome e papel de cada um, em uma linha | nenhum | Frase de posicionamento e equipe |

## Fora do palco (só para perguntas)

- A comparação com o histórico da usina.
- A tentativa de prever o volume.
- O teste de clima perfeito.
- As horas livres. Elas aparecem na tela, mas não são faladas.
- A cobertura de 90–94% das meias-horas com corte. Ela repete o que o 97% já mostra.
- A lista longa de próximos passos.
- Respostas prontas: seção 7 de `docs/premissa-produto.md`.

## O que não dizer

- Que o CurtaMap evita o corte. O corte é uma ordem do operador do sistema.
- Que o operador do sistema não avisa ninguém. Não verificamos isso.
- Que só a IA consegue prever.
- Qualquer valor de economia anual.
- Jargão: "curtailment", "constrained-off", "AP", "recall".

## Vídeo do dashboard (bloco 4)

Os slides serão feitos no Canva e apresentados por link, que permite reproduzir vídeo. O plano
é gravar o dashboard mostrando o aviso de uma usina num dia de setembro.

O vídeo depende de reformular o painel para a premissa sem volume. O painel deve mostrar:

- as janelas em alerta, e não meias-horas soltas;
- a chance de corte;
- o motivo típico com a origem;
- o índice de acerto;
- as horas livres.

Não deve aparecer energia prevista nem a faixa p10–p90.

Se o vídeo não ficar pronto, a alternativa é uma imagem estática do aviso real.
