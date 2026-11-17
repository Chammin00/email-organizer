@echo off
REM Email Organizer CLI convenience wrapper
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0src
set PYTHON_EXE=C:\Users\chase\.venvs\email-organizer\Scripts\python.exe

"%PYTHON_EXE%" -m email_organizer.cli %*
endlocal
