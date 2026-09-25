# Modelo do ambiente da Etapa 2B (Windows). Copie para env.ps1 (ignorado pelo Git), neste
# mesmo diretório, e ajuste $Root para a raiz externa com os dados pesados. O
# execucao/run-step.ps1 carrega ../env.ps1 automaticamente.
$Root = "<disco>:\CurtaMap Etapa 2B"  # no computador dedicado: Y:\CurtaMap Etapa 2B
$env:CURTAMAP_DATA_DIR = "$Root\dados"
$env:CURTAMAP_MODEL_DIR = "$Root\modelos"
$env:CURTAMAP_EXPERIMENT_DIR = "$Root\experimentos"
$env:CURTAMAP_CACHE_DIR = "$Root\cache"
$env:CURTAMAP_TEMP_DIR = "$Root\temporarios"
# Spill/temporários de Python, Polars e bibliotecas nativas fora do C:
$env:TMP = "$Root\temporarios"
$env:TEMP = "$Root\temporarios"
$env:POLARS_TEMP_DIR = "$Root\temporarios\polars"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
