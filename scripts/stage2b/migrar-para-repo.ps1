# Traz a raiz operacional da Etapa 2B para experiments/stage2b no repositório.
# Arquivos pequenos são COPIADOS (a origem não é alterada); diretórios pesados ou não
# versionados ficam na origem e são expostos por junction. Nada é apagado.
# Uso: pwsh -File scripts/stage2b/migrar-para-repo.ps1 [-Source <raiz>] [-Dest <destino>]
param(
    [string] $Source = "Y:\CurtaMap Etapa 2B",
    [string] $Dest = (Join-Path $PSScriptRoot "..\..\experiments\stage2b")
)
$ErrorActionPreference = "Stop"
$Dest = [IO.Path]::GetFullPath($Dest)
New-Item -ItemType Directory -Force $Dest | Out-Null

function Copy-Tree($from, $to, [string[]] $excludeDirs = @()) {
    $args = @($from, $to, "/E", "/COPY:DAT", "/DCOPY:T", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    if ($excludeDirs) { $args += "/XD"; $args += $excludeDirs }
    robocopy @args | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE): $from" }
}

function New-Junction($link, $target) {
    if (-not (Test-Path $target)) { return }
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq "Junction" -and $item.Target -contains $target) { return }
        throw "já existe e não é a junction esperada: $link"
    }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
}

# 1. Operação e handoff (pequenos, copiados integralmente).
Copy-Tree (Join-Path $Source "execucao") (Join-Path $Dest "execucao")
Copy-Tree (Join-Path $Source "handoff") (Join-Path $Dest "handoff")

# 2. Runs: arquivos pequenos copiados; previsões e modelos por junction.
$srcExp = Join-Path $Source "experimentos"
$dstExp = Join-Path $Dest "experimentos"
foreach ($run in Get-ChildItem $srcExp -Directory | Where-Object Name -ne "stage2b-datasets") {
    $to = Join-Path $dstExp $run.Name
    Copy-Tree $run.FullName $to @((Join-Path $run.FullName "predictions"), (Join-Path $run.FullName "models"))
    foreach ($heavy in "predictions", "models") {
        New-Junction (Join-Path $to $heavy) (Join-Path $run.FullName $heavy)
    }
}

# 3. Diretórios inteiros mantidos na origem.
New-Junction (Join-Path $dstExp "stage2b-datasets") (Join-Path $srcExp "stage2b-datasets")
foreach ($dir in "cache", "dados", "sondas", "temporarios") {
    New-Junction (Join-Path $Dest $dir) (Join-Path $Source $dir)
}
Write-Output "migração concluída em $Dest"
