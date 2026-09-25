# Chamado pelo lançador sequencial ANTES de registrar/iniciar o próximo passo.
# Nunca execute este script manualmente enquanto um passo estiver em andamento.
param(
    [Parameter(Mandatory)] [string] $Repo,
    [Parameter(Mandatory)] [string] $RequestPath
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $RequestPath)) { return }
$request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
if ([IO.Path]::GetFullPath($Repo) -ne [IO.Path]::GetFullPath($request.repo)) {
    throw 'A atualização pertence a outro worktree.'
}
$status = git -C $Repo status --porcelain
if ($LASTEXITCODE -ne 0 -or $status) { throw 'Worktree não está limpo para atualizar.' }
$current = git -C $Repo rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível ler HEAD.' }
if ($current -ne $request.expected_commit -and $current -ne $request.target_commit) {
    throw 'HEAD divergiu do commit esperado; atualização cancelada.'
}
if ($current -ne $request.target_commit) {
    git -C $Repo merge --ff-only $request.target_commit
    if ($LASTEXITCODE -ne 0) { throw 'Falha no fast-forward; próximo passo bloqueado.' }
}
$actual = git -C $Repo rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actual -ne $request.target_commit) {
    throw 'Commit aplicado difere do solicitado.'
}
Move-Item -LiteralPath $RequestPath -Destination "$RequestPath.applied"
Write-Output "Código atualizado antes do passo: $actual"
