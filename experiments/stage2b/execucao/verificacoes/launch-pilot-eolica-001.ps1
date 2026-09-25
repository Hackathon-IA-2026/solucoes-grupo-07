. 'Y:\CurtaMap Etapa 2B\env.ps1'
$stepArgs = 'pilot --run-id pilot-eolica-001 --features "Y:\CurtaMap Etapa 2B\experimentos\stage2b-datasets\scenario=noturno_dia_util\source=eolica\round=development\date=*\features.parquet"'
& 'Y:\CurtaMap Etapa 2B\execucao\run-step.ps1' -StepId 'pilot-eolica-001' -Repo 'M:\Bibliotecas\Development\workspaces\hackathon-ia-coppe-2026' -SampleSeconds 30 -Arguments $stepArgs
