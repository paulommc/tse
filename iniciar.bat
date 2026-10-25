@echo off
title TSE 2026 - Central de Apuração e Projeções
echo ============================================================
echo   TSE ELEICOES 2026 - APURACAO PRESIDENCIAL E PROJECOES
echo ============================================================
echo.
echo Iniciando servidor local na porta 8080...
start "" "http://127.0.0.1:8080"
"C:\Users\paulo.mmcastro\AppData\Local\Python\bin\python.exe" server.py
pause
