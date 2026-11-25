$ErrorActionPreference = 'Stop'
$ataflowRoot = Split-Path -Parent $PSScriptRoot
$ataflowPython = Join-Path $ataflowRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $ataflowPython)) {
    throw 'Execute uv sync na pasta do projeto antes de criar o atalho.'
}
$ataflowShell = New-Object -ComObject WScript.Shell
$ataflowDesktop = [Environment]::GetFolderPath('Desktop')
$ataflowShortcut = $ataflowShell.CreateShortcut((Join-Path $ataflowDesktop 'AtaFlow.lnk'))
$ataflowShortcut.TargetPath = $ataflowPython
$ataflowShortcut.Arguments = '-m ataflow'
$ataflowShortcut.WorkingDirectory = $ataflowRoot
$ataflowIcon = Join-Path $ataflowRoot 'assets\icone.ico'
if (Test-Path -LiteralPath $ataflowIcon) {
    $ataflowShortcut.IconLocation = $ataflowIcon
}
$ataflowShortcut.Description = 'AtaFlow'
$ataflowShortcut.Save()
Write-Host 'Atalho do AtaFlow criado na Área de Trabalho.' -ForegroundColor Green
