@echo off
rem ==========================================================================
rem  On Ponto - instalador em um clique (Windows)
rem
rem  1. Encontra um Python 3.12 ou instala o que vem em setup\ (so para este
rem     usuario, sem internet e sem pedir administrador).
rem  2. Entrega o resto para setup\instalar_onponto.py: .venv, bibliotecas
rem     (primeiro as incluidas em setup\wheels), teste com copia dos dados e
rem     atalho na Area de Trabalho.
rem
rem  Mensagens sem acento de proposito: funcionam em qualquer pagina de codigo.
rem  ONPONTO_NO_PAUSE=1 ou ONPONTO_INSTALACAO_AUTOMATICA=1 dispensam a pausa.
rem ==========================================================================
setlocal EnableExtensions DisableDelayedExpansion
title On Ponto - Instalacao
set "RC=1"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto :sem_pasta
set "ROOT=%CD%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONHOME="
set "PYTHONPATH="

if not exist "%ROOT%\setup\instalar_onponto.py" goto :pasta_incompleta
if not exist "%ROOT%\backend\requirements.txt" goto :pasta_incompleta

set "PYEXE="
set "PYARG="
call :procurar_python
if errorlevel 1 call :instalar_python_incluido
if errorlevel 1 call :procurar_python_qualquer
if errorlevel 1 goto :sem_python

"%PYEXE%" %PYARG% "%ROOT%\setup\instalar_onponto.py" %*
set "RC=%ERRORLEVEL%"
goto :fim


rem --------------------------------------------------------------------------
:procurar_python
rem Python 3.12 de 64 bits: o mesmo das bibliotecas incluidas em setup\wheels.
call :testar exata "py" "-3.12" && exit /b 0
call :testar exata "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" && exit /b 0
call :testar exata "%ProgramFiles%\Python312\python.exe" && exit /b 0
call :python_do_registro HKCU && exit /b 0
call :python_do_registro HKLM && exit /b 0
exit /b 1

:procurar_python_qualquer
rem Ultimo recurso: outro Python 3.10+; as bibliotecas virao da internet.
call :testar minima "py" "-3" && exit /b 0
call :testar minima "python" && exit /b 0
call :testar minima "python3" && exit /b 0
exit /b 1

:testar
rem %1 exata ou minima, %2 executavel, %3 argumento opcional (ex.: -3.12)
set "VERIFICACAO=import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)"
if /i "%~1"=="minima" set "VERIFICACAO=import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)"
if not "%~3"=="" goto :testar_com_argumento
"%~2" -c "%VERIFICACAO%" >nul 2>&1
goto :testar_resultado
:testar_com_argumento
"%~2" %~3 -c "%VERIFICACAO%" >nul 2>&1
:testar_resultado
if errorlevel 1 exit /b 1
set "PYEXE=%~2"
set "PYARG=%~3"
exit /b 0

:python_do_registro
set "REGPY="
for /f "tokens=2,*" %%A in ('reg query "%~1\Software\Python\PythonCore\3.12\InstallPath" /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do set "REGPY=%%B"
if defined REGPY call :testar exata "%REGPY%" && exit /b 0
set "REGPY="
for /f "tokens=2,*" %%A in ('reg query "%~1\Software\Python\PythonCore\3.12\InstallPath" /ve 2^>nul ^| findstr /i "REG_SZ"') do set "REGPY=%%B"
if defined REGPY call :testar exata "%REGPY%python.exe" && exit /b 0
exit /b 1

:instalar_python_incluido
set "INSTALADOR=%ROOT%\setup\python-3.12.10-amd64.exe"
if not exist "%INSTALADOR%" exit /b 1
call :windows_64_bits || exit /b 1
echo.
echo Python 3.12 nao encontrado. Instalando o Python incluido no On Ponto:
echo somente para este usuario, sem internet e sem pedir administrador.
echo Aguarde, isso leva cerca de 1 minuto...
call :conferir_instalador
if errorlevel 1 goto :instalador_corrompido
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
"%INSTALADOR%" /quiet InstallAllUsers=0 Include_launcher=1 InstallLauncherAllUsers=0 PrependPath=0 Shortcuts=0 AssociateFiles=0 Include_doc=0 Include_test=0 /log "%ROOT%\logs\python-instalacao.log"
set "RC_PY=%ERRORLEVEL%"
if "%RC_PY%"=="3010" set "RC_PY=0"
if not "%RC_PY%"=="0" goto :instalador_falhou
call :procurar_python
if errorlevel 1 goto :instalador_falhou
echo Python 3.12 instalado.
exit /b 0

:instalador_corrompido
echo AVISO: o instalador do Python em setup\ esta corrompido ou incompleto.
echo Procurando outro Python neste computador...
echo Se nao houver, copie a pasta do On Ponto de novo, completa, ou instale
echo o Python 3.12 de https://www.python.org/downloads/windows/
exit /b 1

:instalador_falhou
echo AVISO: a instalacao do Python nao terminou corretamente (codigo %RC_PY%).
echo Detalhes em logs\python-instalacao.log
exit /b 1

:windows_64_bits
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" exit /b 0
if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" exit /b 0
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" exit /b 0
exit /b 1

:conferir_instalador
rem Compara o SHA-256 do instalador com o registrado em setup\SHA256SUMS.txt.
set "ESPERADO="
for /f "tokens=1" %%H in ('findstr /i /l /c:"python-3.12.10-amd64.exe" "%ROOT%\setup\SHA256SUMS.txt" 2^>nul') do set "ESPERADO=%%H"
if not defined ESPERADO exit /b 1
set "OBTIDO="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%INSTALADOR%" SHA256 2^>nul') do if not defined OBTIDO set "OBTIDO=%%H"
if not defined OBTIDO exit /b 1
set "OBTIDO=%OBTIDO: =%"
if /i "%OBTIDO%"=="%ESPERADO%" exit /b 0
exit /b 1


rem --------------------------------------------------------------------------
:sem_pasta
echo ERRO: nao foi possivel abrir a pasta do On Ponto.
goto :fim

:pasta_incompleta
echo ERRO: esta pasta do On Ponto esta incompleta.
echo Se voce abriu o arquivo de dentro de um ZIP, extraia o ZIP inteiro primeiro
echo (botao direito, "Extrair tudo") e execute instalar_onponto.bat na pasta extraida.
goto :fim

:sem_python
echo.
echo ERRO: nenhum Python 3.10 ou mais novo foi encontrado, e o Python incluido
echo em setup\ nao pode ser instalado neste computador.
echo Instale o Python 3.12 de https://www.python.org/downloads/windows/
echo e execute este arquivo de novo.
goto :fim

:fim
popd >nul 2>&1
echo.
if not defined ONPONTO_NO_PAUSE if not defined ONPONTO_INSTALACAO_AUTOMATICA pause
endlocal & exit /b %RC%
