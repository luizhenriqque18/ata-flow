@echo off
title Criar Atalho - AtaFlow
echo ==========================================
echo Criando atalho na Area de Trabalho...
echo ==========================================

:: Pega o diretorio atual onde o .bat esta rodando
set "PROJECT_DIR=%~dp0"
:: Remove a ultima barra
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: Define o caminho para o icone (pode substituir este arquivo depois)
set "ICON_PATH=%PROJECT_DIR%\icone.ico"

:: Comando PowerShell para criar o .lnk
powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -comObject WScript.Shell; $DesktopPath = [Environment]::GetFolderPath('Desktop'); $ShortcutPath = Join-Path $DesktopPath 'AtaFlow.lnk'; $Shortcut = $WshShell.CreateShortcut($ShortcutPath); $Shortcut.TargetPath = '%PROJECT_DIR%\.venv\Scripts\python.exe'; $Shortcut.Arguments = 'main.py'; $Shortcut.WorkingDirectory = '%PROJECT_DIR%'; if (Test-Path '%ICON_PATH%') { $Shortcut.IconLocation = '%ICON_PATH%' } else { Write-Host 'Aviso: icone.ico nao encontrado na pasta do projeto.' -ForegroundColor Yellow }; $Shortcut.Description = 'AtaFlow'; $Shortcut.Save(); Write-Host ('Atalho criado com sucesso em: ' + $ShortcutPath) -ForegroundColor Green;"

echo.
pause
