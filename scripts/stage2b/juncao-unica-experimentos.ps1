# Substitui as junções por run por UMA junção: experiments/stage2b/experimentos -> raiz externa.
# 1. remove apenas os links das junções internas (nunca remoção recursiva através delas);
# 2. copia os arquivos reais do repositório (leves e modelos) para a raiz externa;
# 3. confere SHA-256 de cada arquivo copiado;
# 4. remove a pasta do repositório e cria a junção única.
param(
    [string] $External = "Y:\CurtaMap Etapa 2B\experimentos",
    [string] $RepoDir = (Join-Path $PSScriptRoot "..\..\experiments\stage2b\experimentos")
)
$ErrorActionPreference = "Stop"
$RepoDir = [IO.Path]::GetFullPath($RepoDir)

$item = Get-Item $RepoDir -Force
if ($item.LinkType -eq "Junction") { Write-Output "já é junção: $RepoDir"; return }

# 1. Links internos.
$links = Get-ChildItem $RepoDir -Recurse -Directory -Force -Attributes ReparsePoint
foreach ($l in $links) { cmd /c rmdir "$($l.FullName)" | Out-Null }
$left = Get-ChildItem $RepoDir -Recurse -Force -Attributes ReparsePoint
if ($left) { throw "restaram reparse points: $($left.FullName -join ', ')" }
Write-Output "links internos removidos: $($links.Count)"

# 2. Cópia para a raiz externa (mescla com as previsões e datasets que já estão lá).
robocopy $RepoDir $External /E /COPY:DAT /DCOPY:T /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }

# 3. Conferência.
$files = Get-ChildItem $RepoDir -Recurse -File -Force
foreach ($f in $files) {
    $rel = [IO.Path]::GetRelativePath($RepoDir, $f.FullName)
    $other = Join-Path $External $rel
    if (-not (Test-Path $other)) { throw "não copiado: $rel" }
    if ((Get-FileHash $f.FullName).Hash -ne (Get-FileHash $other).Hash) { throw "hash difere: $rel" }
}
Write-Output "copiados e conferidos: $($files.Count) arquivos"

# 4. Junção única.
Remove-Item $RepoDir -Recurse -Force
New-Item -ItemType Junction -Path $RepoDir -Target $External | Out-Null
Write-Output "junção criada: $RepoDir -> $External"
