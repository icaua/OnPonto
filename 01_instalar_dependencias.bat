@echo off
setlocal
cd /d "%~dp0"

title On Ponto - Instalacao

echo.
echo ==========================================
echo        ON PONTO - INSTALACAO
echo ==========================================
echo.

REM --------------------------------------------------
REM Localizar Python
REM --------------------------------------------------

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON=py -3"
    goto :python_ok
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON=python"
    goto :python_ok
)

echo [ERRO] Python 3 nao foi encontrado.
echo.
echo Instale o Python 3 antes de continuar.
echo Durante a instalacao, marque:
echo.
echo     Add Python to PATH
echo.
pause
exit /b 1

:python_ok

echo [OK] Python encontrado.

REM --------------------------------------------------
REM Criar ambiente virtual
REM --------------------------------------------------

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Criando ambiente virtual...
    %PYTHON% -m venv .venv

    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel criar o ambiente virtual.
        pause
        exit /b 1
    )
) else (
    echo [OK] Ambiente virtual ja existe.
)

REM --------------------------------------------------
REM Atualizar pip
REM --------------------------------------------------

echo.
echo Atualizando pip...

".venv\Scripts\python.exe" -m pip install --upgrade pip

if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel atualizar o pip.
    echo Verifique sua conexao com a internet.
    pause
    exit /b 1
)

REM --------------------------------------------------
REM Instalar dependencias do On Ponto
REM --------------------------------------------------

echo.
echo Instalando dependencias...

".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"

if errorlevel 1 (
    echo.
    echo [ERRO] Falha na instalacao das dependencias.
    echo.
    echo Verifique:
    echo - conexao com a internet
    echo - bloqueios da rede da empresa
    echo - permissoes do Windows
    echo.
    pause
    exit /b 1
)

REM --------------------------------------------------
REM Verificar instalacao
REM --------------------------------------------------

echo.
echo Verificando dependencias...

".venv\Scripts\python.exe" -m pip check

if errorlevel 1 (
    echo.
    echo [ERRO] Foram encontrados problemas nas dependencias.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo      INSTALACAO CONCLUIDA
echo ==========================================
echo.
echo O ambiente do On Ponto esta pronto.
echo.
echo Agora execute:
echo.
echo     02_iniciar_onponto.bat
echo.
pause
exit /b 0