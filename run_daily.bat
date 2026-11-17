@echo off
REM Email Organizer - Daily Runner Script
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0src
set PYTHON_EXE=C:\Users\chase\.venvs\email-organizer\Scripts\python.exe

echo Running Daily Email Organizer...
"%PYTHON_EXE%" -m email_organizer.cli daily --apply --limit 100
endlocal
