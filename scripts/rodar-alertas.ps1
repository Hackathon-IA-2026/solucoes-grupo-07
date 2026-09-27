param(
    [string]$Fonte = 'fotovoltaica',
    [string]$Inicio = '2026-08-01',
    [string]$Fim = '2026-08-31',
    [int]$TreinoDias = 365,
    [string]$Dados = 'data',
    [string]$Saida = 'data/interim/alertas',
    [int]$MaxSegundos = 1200,
    [double]$MaxGiB = 3
)
$ErrorActionPreference = 'Stop'
$env:OMP_NUM_THREADS = '2'
$env:POLARS_MAX_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:PYTHONIOENCODING = 'utf-8'
$repoAlertas = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoAlertas
New-Item -ItemType Directory -Force -Path $Saida | Out-Null
$destinoAlertas = (Resolve-Path -LiteralPath $Saida).Path
$prefixoAlertas = Join-Path $destinoAlertas "${Fonte}_${Inicio}_${Fim}"
$argumentosAlertas = @('-m', 'curtamap.previsao.alertas', $Inicio, $Fim,
    '--fonte', $Fonte, '--treino-dias', "$TreinoDias",
    '--dados', ('"{0}"' -f $Dados), '--saida', ('"{0}"' -f $destinoAlertas))
$cronometroAlertas = [Diagnostics.Stopwatch]::StartNew()
$processoAlertas = Start-Process -FilePath '.venv/Scripts/python.exe' -ArgumentList $argumentosAlertas `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput "$prefixoAlertas.stdout.log" `
    -RedirectStandardError "$prefixoAlertas.stderr.log"
$picoPrivadoAlertas = 0L
$picoRamAlertas = 0L
$interrompidoAlertas = $false
while (-not $processoAlertas.HasExited) {
    $processoAlertas.Refresh()
    # No Windows o python.exe do venv pode ser um launcher; conte também os filhos.
    $arvoreAlertas = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $idsAlertas = [Collections.Generic.HashSet[int]]::new()
    [void]$idsAlertas.Add($processoAlertas.Id)
    do {
        $antesAlertas = $idsAlertas.Count
        foreach ($itemAlertas in $arvoreAlertas) {
            if ($idsAlertas.Contains([int]$itemAlertas.ParentProcessId)) {
                [void]$idsAlertas.Add([int]$itemAlertas.ProcessId)
            }
        }
    } while ($idsAlertas.Count -gt $antesAlertas)
    $familiaAlertas = @(Get-Process -Id @($idsAlertas) -ErrorAction SilentlyContinue)
    $privadoAlertas = ($familiaAlertas | Measure-Object PrivateMemorySize64 -Sum).Sum
    $ramAlertas = ($familiaAlertas | Measure-Object WorkingSet64 -Sum).Sum
    $picoPrivadoAlertas = [Math]::Max($picoPrivadoAlertas, $privadoAlertas)
    $picoRamAlertas = [Math]::Max($picoRamAlertas, $ramAlertas)
    if ($picoPrivadoAlertas -gt ($MaxGiB * 1GB) -or $cronometroAlertas.Elapsed.TotalSeconds -gt $MaxSegundos) {
        $familiaAlertas | Stop-Process -ErrorAction SilentlyContinue
        $interrompidoAlertas = $true
        break
    }
    Start-Sleep -Seconds 1
}
$processoAlertas.WaitForExit()
$cronometroAlertas.Stop()
@{
    segundos = $cronometroAlertas.Elapsed.TotalSeconds
    pico_memoria_privada_bytes = $picoPrivadoAlertas
    pico_ram_bytes = $picoRamAlertas
    limite_gib = $MaxGiB
    limite_segundos = $MaxSegundos
    amostragem_segundos = 1
    interrompido = $interrompidoAlertas
    exit_code = $processoAlertas.ExitCode
} | ConvertTo-Json | Set-Content -LiteralPath "$prefixoAlertas.recursos.json" -Encoding utf8
Get-Content -LiteralPath "$prefixoAlertas.stdout.log"
Get-Content -LiteralPath "$prefixoAlertas.stderr.log"
if ($interrompidoAlertas) { throw 'Execução interrompida por limite de recursos' }
if ($processoAlertas.ExitCode -ne 0) { throw "Execução falhou: $($processoAlertas.ExitCode)" }
