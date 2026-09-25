# Registra (ou atualiza) uma tarefa do Agendador de Tarefas que executa um script PowerShell
# fora da árvore de processos de qualquer aplicativo (Codex, Claude, terminal).
# Motivo: processos lançados de um shell do app herdam o Job Object dele e morrem quando o app é
# encerrado ou atualizado. Sob o Agendador, o pai é o serviço Schedule.
# Uso: pwsh -File register-queue-task.ps1 -TaskName CurtaMap-Fila-2B -Script <ps1> -LogPath <log> [-Start]
# Limites: logon Interactive (sem senha armazenada) -> logoff ou reinício do Windows ainda encerram a tarefa.
param(
    [Parameter(Mandatory)] [string] $TaskName,
    [Parameter(Mandatory)] [string] $Script,
    [Parameter(Mandatory)] [string] $LogPath,
    [switch] $Start
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Script)) { throw "script não encontrado: $Script" }
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and $existing.State -eq 'Running') { throw "tarefa $TaskName já está em execução; não registro por cima" }

$pwsh = (Get-Command pwsh).Source
# A saída do próprio pwsh da tarefa vai para um log: erros anteriores ao primeiro Log() não somem.
$command = "& '$($Script.Replace("'", "''"))' *>> '$($LogPath.Replace("'", "''"))'"
$action = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$command`"" `
    -WorkingDirectory (Split-Path -Parent $Script)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
# Priority 4 = normal (o padrão 7 rebaixa CPU, I/O e memória); sem limite de 72 h; sem gatilho,
# para que só um disparo explícito inicie a fila (nada de retomada automática no logon).
$settings = New-ScheduledTaskSettingsSet -Priority 4 -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd `
    -MultipleInstances IgnoreNew -StartWhenAvailable:$false
Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Settings $settings `
    -Description 'CurtaMap: execução durável fora do ciclo de vida do aplicativo.' -Force | Out-Null
if ($Start) { Start-ScheduledTask -TaskName $TaskName }
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
