@echo off
rem Nome antigo, mantido para quem ainda segue instrucoes anteriores.
rem O instalador oficial e instalar_onponto.bat.
call "%~dp0instalar_onponto.bat" %*
exit /b %ERRORLEVEL%
