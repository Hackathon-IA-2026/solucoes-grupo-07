# Roadmap do Zelo

Este roadmap indica direção e critérios de passagem. Ele não fixa algoritmos, telas ou serviços antes de termos evidência suficiente.

## 1. Fundamentos e dados

- Automatizar a aquisição das bases e registrar sua procedência.
- Auditar schema, cobertura, duplicidade, frequência e distribuição temporal.
- Validar a definição de curtailment e os rótulos de causa.
- Produzir as primeiras evidências do problema e do “por que agora?”.

**Saída:** contrato de dados testado, relatório exploratório e fórmula de alvo defensável.

## 2. Baselines e protocolo experimental

- Definir cortes temporais e métricas antes de treinar modelos candidatos.
- Implementar baselines simples e reproduzíveis.
- Comparar famílias de modelos sem vazamento temporal.
- Documentar desempenho, custo, latência e limitações.

**Saída:** escolha fundamentada para ocorrência, volume e causa.

## 3. Recomendação e impacto

- Relacionar cada causa a ações possíveis e limites operacionais.
- Implementar cenários de recuperação de energia.
- Tornar explícitas as premissas financeiras e de carbono.
- Validar se as recomendações são úteis para o gerador.

**Saída:** fluxo rastreável de previsão até decisão e impacto.

## 4. Experiência e narrativa

- Executar um spike Streamlit versus React/FastAPI.
- Escolher a interface a partir de esforço, liberdade visual e risco de entrega.
- Construir o fluxo operacional, o resumo tático e o assistente contextual opcional.
- Testar a demonstração com uma história de usuário realista.

**Saída:** experiência demonstrável e coerente com o pitch.

## 5. AWS e operação

- Validar permissões e custos com um stack mínimo em CDK.
- Automatizar build, armazenamento, execução e observabilidade.
- Implantar a aplicação a partir deste único repositório.
- Exercitar recuperação, desligamento e reprodução do ambiente.

**Saída:** demo reproduzível na AWS sem etapas manuais ocultas.

## 6. Validação final e apresentação

- Reexecutar todos os experimentos e testes com artefatos versionados.
- Consolidar evidências, limitações, impacto e próximos passos.
- Ensaiar perguntas técnicas e de negócio.
- Preparar contingência offline para a demonstração.

**Saída:** entrega verificável e narrativa de negócio sustentada por dados.
