# Modelo do ambiente da Etapa 2B (Windows). Copie para env.ps1 (ignorado pelo Git) neste
# diretório e ajuste $External. O execucao/run-step.ps1 carrega ../env.ps1 automaticamente.
$Repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$External = "<disco>:\CurtaMap Etapa 2B"  # no computador dedicado: Y:\CurtaMap Etapa 2B
$env:CURTAMAP_DATA_DIR = "$PSScriptRoot\dados"
$env:CURTAMAP_CACHE_DIR = "$PSScriptRoot\cache"
$env:CURTAMAP_MODEL_DIR = "$Repo\models"
# experimentos é junção para $External\experimentos (não cabe no disco do repositório).
$env:CURTAMAP_EXPERIMENT_DIR = "$PSScriptRoot\experimentos"
# Spill de Python, Polars e bibliotecas nativas: pode chegar a dezenas de GB.
$env:CURTAMAP_TEMP_DIR = "$External\temporarios"
$env:TMP = "$External\temporarios"
$env:TEMP = "$External\temporarios"
$env:POLARS_TEMP_DIR = "$External\temporarios\polars"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
