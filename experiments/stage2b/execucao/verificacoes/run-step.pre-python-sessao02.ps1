# Executa um passo pesado da Etapa 2B de forma durável e auditável.
# Uso: pwsh -File run-step.ps1 -StepId <id único> -Repo <repo> -Arguments <args do curtamap-experiment>
param(
    [Parameter(Mandatory)] [string] $StepId,
    [Parameter(Mandatory)] [string] $Repo,
    [Parameter(Mandatory)] [string] $Arguments,
    [string] $ExperimentDirOverride = "",
    [int] $SampleSeconds = 30
)
$ErrorActionPreference = "Stop"
. "Y:\CurtaMap Etapa 2B\env.ps1"
if ($ExperimentDirOverride) { $env:CURTAMAP_EXPERIMENT_DIR = $ExperimentDirOverride }
$stepDir = Join-Path "Y:\CurtaMap Etapa 2B\execucao\passos" $StepId
if (Test-Path $stepDir) { throw "passo já existe, não sobrescrevo: $stepDir" }
New-Item -ItemType Directory -Force $stepDir | Out-Null

$uv = (Get-Command uv).Source
$full = "uv run curtamap-experiment --config configs/experimental/stage2b.example.json $Arguments"
$meta = [ordered]@{
    step_id = $StepId
    command = $full
    cwd = $Repo
    code_commit = (git -C $Repo rev-parse HEAD)
    git_status_short = (git -C $Repo status --short) -join "`n"
    env = @{
        CURTAMAP_DATA_DIR = $env:CURTAMAP_DATA_DIR; CURTAMAP_MODEL_DIR = $env:CURTAMAP_MODEL_DIR
        CURTAMAP_EXPERIMENT_DIR = $env:CURTAMAP_EXPERIMENT_DIR; CURTAMAP_CACHE_DIR = $env:CURTAMAP_CACHE_DIR
        CURTAMAP_TEMP_DIR = $env:CURTAMAP_TEMP_DIR; TMP = $env:TMP; POLARS_TEMP_DIR = $env:POLARS_TEMP_DIR
    }
    started_at = (Get-Date).ToString("o")
}
$full | Set-Content (Join-Path $stepDir "command.txt") -Encoding utf8

$proc = Start-Process -FilePath $uv `
    -ArgumentList "run curtamap-experiment --config configs/experimental/stage2b.example.json $Arguments" `
    -WorkingDirectory $Repo -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $stepDir "stdout.log") `
    -RedirectStandardError (Join-Path $stepDir "stderr.log")
$null = $proc.Handle  # garante acesso ao ExitCode depois
$meta.pid = $proc.Id
$meta | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $stepDir "start.json") -Encoding utf8
$proc.Id | Set-Content (Join-Path $stepDir "pid.txt")

function Get-Tree([int] $RootId) {
    $all = Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, WorkingSetSize, Name
    $ids = [System.Collections.Generic.List[int]]::new(); $ids.Add($RootId)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($p in $all) { if ($ids.Contains([int]$p.ParentProcessId) -and -not $ids.Contains([int]$p.ProcessId)) { $ids.Add([int]$p.ProcessId); $changed = $true } }
    }
    $all | Where-Object { $ids.Contains([int]$_.ProcessId) }
}
$samples = Join-Path $stepDir "samples.csv"
"timestamp,tree_working_set_bytes,max_process_peak_ws_bytes,free_bytes_Y,free_bytes_C" | Set-Content $samples
$peakTree = 0; $peakProc = 0
while (-not $proc.HasExited) {
    try {
        $tree = Get-Tree $proc.Id
        $ws = ($tree | Measure-Object WorkingSetSize -Sum).Sum
        $pk = 0
        foreach ($t in $tree) { try { $v = (Get-Process -Id $t.ProcessId -ErrorAction Stop).PeakWorkingSet64; if ($v -gt $pk) { $pk = $v } } catch {} }
        if ($ws -gt $peakTree) { $peakTree = $ws }; if ($pk -gt $peakProc) { $peakProc = $pk }
        $fy = (Get-PSDrive Y).Free; $fc = (Get-PSDrive C).Free
        "$((Get-Date).ToString('o')),$ws,$pk,$fy,$fc" | Add-Content $samples
    } catch {}
    Start-Sleep -Seconds $SampleSeconds
}
$proc.WaitForExit()
$end = [ordered]@{
    step_id = $StepId
    pid = $proc.Id
    exit_code = $proc.ExitCode
    started_at = $meta.started_at
    finished_at = (Get-Date).ToString("o")
    duration_seconds = [math]::Round(((Get-Date) - [datetime]$meta.started_at).TotalSeconds, 1)
    peak_tree_working_set_bytes_sampled = $peakTree
    peak_process_working_set_bytes = $peakProc
}
$end | ConvertTo-Json | Set-Content (Join-Path $stepDir "end.json") -Encoding utf8
