@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1
title On Ponto

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERRO: Não foi possível acessar a pasta do On Ponto.
    call :pausar
    exit /b 1
)

set "ROOT=%CD%"
set "VENV_PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "FRONTEND_URL=http://127.0.0.1:5500/"
set "API_URL=http://127.0.0.1:8000/"

if not exist "%VENV_PYTHON%" (
    echo.
    echo Ambiente do On Ponto não encontrado. Execute instalar_onponto.bat primeiro.
    goto :erro
)

if not exist "%BACKEND_DIR%\app\main.py" (
    echo.
    echo ERRO: O backend do On Ponto não foi encontrado.
    goto :erro
)

if not exist "%FRONTEND_DIR%\index.html" (
    echo.
    echo ERRO: O frontend do On Ponto não foi encontrado.
    goto :erro
)

"%VENV_PYTHON%" -c "import fastapi, openpyxl, sqlalchemy, uvicorn, multipart" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERRO: As dependências do On Ponto não estão instaladas corretamente.
    echo Execute instalar_onponto.bat novamente.
    goto :erro
)

call :porta_livre 8000
if errorlevel 1 (
    echo.
    echo ERRO: A porta 8000 já está ocupada.
    echo Feche o programa que usa essa porta e tente novamente.
    goto :erro
)

call :porta_livre 5500
if errorlevel 1 (
    echo.
    echo ERRO: A porta 5500 já está ocupada.
    echo Feche o programa que usa essa porta e tente novamente.
    goto :erro
)

echo Iniciando API...
start "On Ponto API" /D "%BACKEND_DIR%" "%ComSpec%" /D /K ""%VENV_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
if errorlevel 1 (
    echo ERRO: Não foi possível abrir a janela da API.
    goto :erro
)

echo Iniciando frontend...
start "On Ponto Frontend" /D "%FRONTEND_DIR%" "%ComSpec%" /D /K ""%VENV_PYTHON%" -m http.server 5500 --bind 127.0.0.1"
if errorlevel 1 (
    echo ERRO: Não foi possível abrir a janela do frontend.
    goto :erro
)

echo Aguardando os serviços iniciarem...
timeout /t 2 /nobreak >nul 2>&1

for /L %%I in (1,1,20) do (
    "%VENV_PYTHON%" -c "import urllib.request; urllib.request.urlopen('%API_URL%', timeout=1).close()" >nul 2>&1
    if not errorlevel 1 goto :api_pronta
    timeout /t 1 /nobreak >nul 2>&1
)
goto :api_indisponivel

:api_pronta
for /L %%I in (1,1,10) do (
    "%VENV_PYTHON%" -c "import urllib.request; urllib.request.urlopen('%FRONTEND_URL%', timeout=1).close()" >nul 2>&1
    if not errorlevel 1 goto :frontend_pronto
    timeout /t 1 /nobreak >nul 2>&1
)
goto :frontend_indisponivel

:frontend_pronto
if not defined ONPONTO_NO_BROWSER start "" "%FRONTEND_URL%"

echo.
echo On Ponto iniciado
echo.
echo Frontend:
echo http://127.0.0.1:5500
echo.
echo API:
echo http://127.0.0.1:8000
echo.
echo Swagger:
echo http://127.0.0.1:8000/docs
echo.
popd
call :pausar
exit /b 0

:api_indisponivel
echo.
echo ERRO: A API não respondeu em http://127.0.0.1:8000.
echo Consulte a janela "On Ponto API" para ver o erro.
echo Feche manualmente as janelas abertas antes de tentar novamente.
goto :erro

:frontend_indisponivel
echo.
echo ERRO: O frontend não respondeu em http://127.0.0.1:5500.
echo Consulte a janela "On Ponto Frontend" para ver o erro.
echo Feche manualmente as janelas abertas antes de tentar novamente.
goto :erro

:erro
echo.
popd
call :pausar
exit /b 1

:porta_livre
"%VENV_PYTHON%" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', %~1)); s.close()" >nul 2>&1
exit /b %errorlevel%

:pausar
if not defined ONPONTO_NO_PAUSE pause
exit /b 0
