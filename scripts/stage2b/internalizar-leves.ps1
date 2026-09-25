# Traz para dentro do repositório os diretórios não versionados que cabem no disco
# (modelos das runs, cache, dados brutos e sondas), que antes eram junctions para a raiz
# externa. Para cada diretório:
#   1. remove a junction do repositório (só o link; o alvo não é tocado);
#   2. copia o conteúdo real para o repositório;
#   3. confere SHA-256 arquivo a arquivo contra a origem;
#   4. só então remove a origem e cria, no lugar dela, uma junction inversa apontando para
#      o repositório, para que os caminhos absolutos já gravados em relatórios continuem válidos.
# Previsões, datasets e temporários continuam na raiz externa.
param(
    [string] $Source = "Y:\CurtaMap Etapa 2B",
    [string] $Dest = (Join-Path $PSScriptRoot "..\..\experiments\stage2b")
)
$ErrorActionPreference = "Stop"
$Dest = [IO.Path]::GetFullPath($Dest)

function Get-Hashes($root) {
    $map = @{}
    Get-ChildItem $root -Recurse -File -Force | ForEach-Object {
        $map[[IO.Path]::GetRelativePath($root, $_.FullName)] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    }
    return $map
}

function Move-IntoRepo($repoPath, $sourcePath) {
    $sourceItem = Get-Item $sourcePath -Force
    if ($sourceItem.LinkType -eq "Junction") { Write-Output "já convertido: $sourcePath"; return }
    $repoItem = Get-Item $repoPath -Force -ErrorAction SilentlyContinue
    if ($repoItem -and $repoItem.LinkType -eq "Junction") {
        cmd /c rmdir "$repoPath" | Out-Null   # remove só o link
    } elseif ($repoItem) {
        throw "destino existe e não é junction: $repoPath"
    }
    robocopy $sourcePath $repoPath /E /COPY:DAT /DCOPY:T /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE): $sourcePath" }
    $a = Get-Hashes $sourcePath
    $b = Get-Hashes $repoPath
    if ($a.Count -ne $b.Count) { throw "contagem difere: $sourcePath ($($a.Count) vs $($b.Count))" }
    foreach ($k in $a.Keys) {
        if ($a[$k] -ne $b[$k]) { throw "hash difere: $sourcePath\$k" }
    }
    Remove-Item $sourcePath -Recurse -Force
    New-Item -ItemType Junction -Path $sourcePath -Target $repoPath | Out-Null
    Write-Output ("movido: {0} ({1} arquivos, hashes iguais)" -f $sourcePath, $a.Count)
}

Get-ChildItem (Join-Path $Source "experimentos") -Directory | ForEach-Object {
    $models = Join-Path $_.FullName "models"
    if (Test-Path $models) {
        Move-IntoRepo (Join-Path $Dest "experimentos\$($_.Name)\models") $models
    }
}
foreach ($dir in "cache", "dados", "sondas") {
    Move-IntoRepo (Join-Path $Dest $dir) (Join-Path $Source $dir)
}
