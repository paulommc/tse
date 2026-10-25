@echo off
cd /d "%~dp0"
title TSE 2026 - Central de Apuracao e Projecoes
echo ============================================================
echo   TSE ELEICOES 2026 - APURACAO PRESIDENCIAL E PROJECOES
echo ============================================================
echo.
echo Iniciando servidor local na porta 8080...

:: Abre o navegador com pequeno delay para dar tempo ao servidor iniciar
start /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8080"

"C:\Users\paulo.mmcastro\AppData\Local\Python\bin\python.exe" server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Tentando executar com o executavel 'python' do PATH...
    python server.py
)
pause

