# Mostra o andamento da fila da Etapa 2B. Uso: pwsh -File "Y:\CurtaMap Etapa 2B\execucao\status-fila.ps1"
# Um passo só aparece como RODANDO se o processo registrado existir com a MESMA hora de criação;
# PID reutilizado por outro programa não conta. Passo sem end.json e sem processo = INTERROMP.
$Root = 'Y:\CurtaMap Etapa 2B'
$log = "$Root\execucao\fila\fila.log"
$TaskName = 'CurtaMap-Fila-2B'

function Test-Alive([int] $ProcessId, [string] $CreatedAt, [double] $ToleranceSeconds) {
  if (-not $ProcessId -or -not $CreatedAt) { return $false }
  $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  if (-not $p) { return $false }
  [math]::Abs(($p.StartTime - [datetime]$CreatedAt).TotalSeconds) -le $ToleranceSeconds
}

$ids = @('main-eolica-v1-002','main-eolica-v2-001','main-eolica-v2-002','main-eolica-v2-003','main-eolica-v2-004','main-eolica-v3-001','main-eolica-v4-001',
  'main-fotovoltaica-v1-001','main-fotovoltaica-v2-001','main-fotovoltaica-v3-001','main-fotovoltaica-v4-001',
  'features-noturno_mais_24h-eolica-development-001','check-noturno_mais_24h-eolica-001',
  'delay-eolica-v1-001','delay-eolica-v2-001','delay-eolica-v3-001','delay-eolica-v4-001',
  'features-noturno_mais_24h-fotovoltaica-development-001','check-noturno_mais_24h-fotovoltaica-001',
  'delay-fotovoltaica-v1-001','delay-fotovoltaica-v2-001','delay-fotovoltaica-v3-001','delay-fotovoltaica-v4-001')
foreach ($id in $ids) {
  $dir = "$Root\execucao\passos\$id"
  if (Test-Path "$dir\end.json") {
    $e = Get-Content "$dir\end.json" -Raw | ConvertFrom-Json
    $m = "$Root\experimentos\$id\manifest.json"
    $st = if (Test-Path $m) { (Get-Content $m -Raw | ConvertFrom-Json).status } else { '-' }
    $s = if ($e.interrupted_by_user) { 'CANCEL.' } elseif ($e.exit_code -eq 0) { 'OK' } else { 'FALHOU' }
    '{0,-8} {1,-55} {2,6:N1} h  exit={3} status={4}' -f $s, $id, ($e.duration_seconds / 3600), $e.exit_code, $st
  } elseif (Test-Path "$dir\start.json") {
    $j = Get-Content "$dir\start.json" -Raw | ConvertFrom-Json
    # Registros novos têm pid_started_at exato; os antigos só têm started_at (margem maior).
    $vivo = if ($j.pid_started_at) { Test-Alive $j.pid $j.pid_started_at 2 } else { Test-Alive $j.pid $j.started_at 15 }
    $ultima = if (Test-Path "$dir\samples.csv") { (Get-Content "$dir\samples.csv" -Tail 1).Split(',')[0] } else { '-' }
    if ($vivo) { '{0,-8} {1,-55} desde {2}; última amostra {3}' -f 'RODANDO', $id, $j.started_at, $ultima }
    else { '{0,-8} {1,-55} desde {2}; processo ausente; última amostra {3}' -f 'INTERROMP', $id, $j.started_at, $ultima }
  } else { '{0,-8} {1}' -f 'PENDENTE', $id }
}

$ativa = $false
if (Test-Path "$Root\execucao\fila\fila.lock.json") {
  $lock = Get-Content "$Root\execucao\fila\fila.lock.json" -Raw | ConvertFrom-Json
  $ativa = Test-Alive $lock.pid $lock.started_at 2
}
''
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
  $info = $task | Get-ScheduledTaskInfo
  'Tarefa agendada {0}: estado={1}; última execução={2}; último resultado=0x{3:X}' -f $TaskName, $task.State, $info.LastRunTime, $info.LastTaskResult
} else { "Tarefa agendada $TaskName não registrada." }
if ($ativa) { 'Fila ativa.' }
else {
  $filaLinhas = @(Get-Content $log -ErrorAction SilentlyContinue)
  $ultimoEvento = $filaLinhas | Where-Object { $_ -match 'fila iniciada|fila concluída|fila interrompida|PARAR:' } | Select-Object -Last 1
  if ($ultimoEvento -match 'fila concluída com sucesso') { 'FILA CONCLUÍDA COM SUCESSO.' }
  elseif ($ultimoEvento -match 'fila interrompida') { 'ATENÇÃO: fila interrompida após falha (veja fila.log).' }
  elseif ($ultimoEvento -match 'PARAR:') { 'Fila parada com segurança por solicitação.' }
  else { 'ATENÇÃO: fila não está rodando e a execução mais recente não concluiu (veja fila.log).' }
}
'Últimas linhas do log:'; Get-Content $log -Tail 4
