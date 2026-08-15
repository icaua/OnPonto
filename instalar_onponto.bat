@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1
title Instalação do On Ponto

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERRO: Não foi possível acessar a pasta do On Ponto.
    call :pausar
    exit /b 1
)

set "ROOT=%CD%"
set "VENV_DIR=%ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS=%ROOT%\backend\requirements.txt"

if not exist "%REQUIREMENTS%" (
    echo.
    echo ERRO: backend\requirements.txt não foi encontrado.
    goto :erro
)

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERRO: O ambiente .venv está danificado ou usa Python anterior ao 3.10.
        echo Renomeie ou remova a pasta .venv e execute este instalador novamente.
        goto :erro
    )
    echo Ambiente virtual existente encontrado.
    goto :instalar_dependencias
)

if exist "%VENV_DIR%" (
    echo.
    echo ERRO: A pasta .venv existe, mas não contém Scripts\python.exe.
    echo Renomeie ou remova a pasta .venv e execute este instalador novamente.
    goto :erro
)

set "PYTHON_EXE="
set "PYTHON_ARGS="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
)

if not defined PYTHON_EXE (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo.
    echo ERRO: Python 3.10 ou superior não foi encontrado.
    echo Instale o Python 3 para Windows e execute este arquivo novamente.
    goto :erro
)

echo Criando ambiente virtual em .venv...
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo.
    echo ERRO: Não foi possível criar o ambiente virtual .venv.
    goto :erro
)

if not exist "%VENV_PYTHON%" (
    echo.
    echo ERRO: O ambiente virtual não foi criado corretamente.
    goto :erro
)

:instalar_dependencias
"%VENV_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERRO: O ambiente .venv está incompleto e não contém pip.
    echo Renomeie ou remova a pasta .venv e execute este instalador novamente.
    goto :erro
)

echo Instalando dependências do On Ponto...
"%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo.
    echo ERRO: Não foi possível instalar as dependências.
    echo Verifique sua conexão e as mensagens acima.
    goto :erro
)

echo.
echo On Ponto instalado com sucesso.
echo Execute iniciar_onponto.bat para abrir o sistema.
echo.
popd
call :pausar
exit /b 0

:erro
echo.
echo A instalação do On Ponto não foi concluída.
echo.
popd
call :pausar
exit /b 1

:pausar
if not defined ONPONTO_NO_PAUSE pause
exit /b 0
