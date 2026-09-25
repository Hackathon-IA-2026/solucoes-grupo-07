# Etapa 2B — relatório factual em construção

Atualização: 23/09/2026. INCOMPLETO; não autoriza escolha de modelo nem teste reservado.

## 1. Estado e escopo

Marco 1 (piloto eólico) concluído tecnicamente; marco 2 (populações/contingência) em preparação. Marcos 3–7 pendentes. Das 18 runs, somente pilot-eolica-001 concluída.

## 2. Proveniência

Retomada em 48bc71a39c411c2c8725a744cdf3548baf7e3b9e. Dataset eólico principal gerado em 70a181d; verificado em a5b4a87. Piloto e auditoria no 48bc71a. Registro documental 7f56c88. Índice externo: execucao/run-index.json. Arquivos originais preservados.

## 3. Ambiente

Windows 11, Python 3.12.12, CPU Ryzen 5 5600X, 32 GB RAM. Ambiente externo env.ps1; processos pesados pelo run-step.ps1, um por vez. LightGBM efetivo n_jobs=1; configuração threads=6 é divergência conhecida ainda não alterada.

## 4. Protocolo e desvios

Protocolo Etapa 2A, V1–V4, seed42, duas famílias/quatro tarefas. Sem amostragem aprovada ou implementada nesta sessão. Usuário autorizou desenvolvimento e commits locais no computador dedicado, sobrepondo separação anterior do Mac. Sem push/merge main. Teste reservado bloqueado.

## 5. Datasets e contratos

Eólico principal aprovado: 339.738.048 features, 1.358.952.192 baselines, 942 partições, 180 entidades, 18 checks aprovados. 01/10/2023 legitimamente vazio. 172.584 tau de fronteira, ZERO após filtros reais V1–V4. Geração/verificação aprovada não foi refeita. Solar principal, eólico +24h e solar +24h pendentes.

## 6. Pilotos

Eólico: 8 fits, failures=[], stderr vazio, exit0. 500.000 exemplos por ocorrência/família; 191.505 volume e 269.514 causa. Executor 60,5s (amostragem30s); manifesto ~35,5s. Pico processo1.719.541.760B; árvore amostrada1.666.011.136B. Run3.706.035B. Auditoria: 10 hashes, 8 recargas e contratos de 256 saídas/modelo aprovados. Head2M contém 02–08/10/2023 e ZERO elegíveis por histórico. Piloto é exclusivamente técnico, não representativo do treino completo. Solar pendente.

## 7. Populações e cortes

Medição exata pendente. Distinguir _range+_task_filter do treino e _validation_filter do painel aberto. Quatro trechos de treino de ocorrência coexistem; leitura lazy não remove custo da matriz do fit. Nenhuma projeção de tempo do piloto será tratada como previsão da campanha.

## 8. Execução principal

0/8 runs iniciadas; dependem de medição, decisão de recursos e datasets/pilotos.

## 9. Baselines e resultados factuais

Sem métricas preditivas externas. Não existe vencedor. Limitações preservadas: limiar baseline0,5 e expressão threshold or0.5; subset8 numéricas+4 categóricas; avaliação do volume condicional sobre validação completa válida, não somente cortes positivos.

## 10. Calibração e limiares

Nenhum calibrador/limiar de campanha ajustado. Procedimento interno permanece congelado no protocolo.

## 11. Diagnósticos e cobertura

Nenhum diagnóstico preditivo executado. Limitações conhecidas: elegibilidade usa t0, não c(t0); IDs sem fonte são usados apenas dentro de uma fonte; recortes idade dos baselines refletem idade do comparador. Warnings históricos preservados.

## 12. Sensibilidade

0/8 sensibilidades iniciadas. Obrigatórias com --frozen-run e sem retreino, recalibração ou novos limiares. Limitação conhecida: entity_new/panel_fixed fixados False na implementação atrasada; painel_aberto global.

## 13. Recursos, falhas e retomada

Falhas históricas preservadas no handoff sessão01 e run-index. Piloto desta sessão sem falha. Checkpoint: execucao/CHECKPOINT-sessao-03.md. Suíte documental pilot-report-pytest-001:208passed/81warnings/118,39s; Ruffcheck/format aprovados. Warnings da suíte não são warnings do piloto.

## 14. Integridade e inventário

Inventário final pendente. Checksums do piloto conferidos em execucao/verificacoes/audit-pilot-eolica-001.json. Não alterar artefatos de runs finalizados.

## 15. Pendências e handoff 2C

Campanha incompleta; não iniciar análise de escolha 2C. Próximo: medir populações, consolidar uma decisão de contingência e threads; gerar/verificar restantes; piloto solar; principais e sensibilidades; inventário e fechamento. Reportar qualquer falha de contrato antes de avançar.
