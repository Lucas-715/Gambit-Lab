@echo off
title Gambit Lab
echo ========================================================
echo               GAMBIT LAB NOCTURNE
echo ========================================================
echo.
echo Verificando se a porta 8000 ja esta em uso...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo Iniciando o servidor local em http://127.0.0.1:8000 ...
echo.

rem Abre o navegador automaticamente apos 2 segundos
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"

rem Executa o servidor FastAPI com o Python do ambiente virtual
.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload

pause

