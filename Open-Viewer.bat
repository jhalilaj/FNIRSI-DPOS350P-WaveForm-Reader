@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" src\app.py %*
) else if exist "..\..\work\qt-env\Scripts\python.exe" (
  "..\..\work\qt-env\Scripts\python.exe" src\app.py %*
) else (
  python src\app.py %*
)
if errorlevel 1 pause
