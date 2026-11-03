@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Automatic Meme Video Generator - Installer

 echo ================================================
 echo   Installing Automatic Meme Video Generator
 echo ================================================
 echo.

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if errorlevel 1 goto no_python
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if errorlevel 1 goto old_python
    set "PYTHON_CMD=python"
)

echo [1/4] Checking Python...
%PYTHON_CMD% -c "import sys; print('Using Python', sys.version)"
if errorlevel 1 goto failed

echo.
echo [2/4] Creating the virtual environment...
echo This step creates the .venv folder inside this project.
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto failed
) else (
    echo An existing virtual environment was found. Reusing it.
)
if not exist ".venv\Scripts\python.exe" goto failed

 echo.
 echo [3/4] Updating pip...
 ".venv\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check
 if errorlevel 1 goto failed

 echo.
 echo [4/4] Installing the project and its packages...
 echo Some video packages are large. Pip will show download progress below.
 ".venv\Scripts\python.exe" -m pip install -e . --progress-bar on
 if errorlevel 1 goto failed

if not exist ".env" copy ".env.example" ".env" >nul
if not exist "assets\gameplay" mkdir "assets\gameplay"
if not exist "output" mkdir "output"

echo.
echo ================================================
echo Installation complete.
echo ================================================
echo 1. Add your gameplay videos to assets\gameplay
echo 2. For Reddit mode, fill in your Reddit API credentials in .env
echo 3. Run run.bat
 echo.
pause
exit /b 0

:no_python
echo Python 3.10 or newer was not found.
echo Install Python 3.10 or newer, enable the Python launcher or Add Python to PATH, then reopen this installer.
pause
exit /b 1

:old_python
echo The available Python version is older than 3.10.
echo Install Python 3.10 or newer, then reopen this installer.
pause
exit /b 1

:failed
echo.
echo Installation stopped because one of the steps above failed.
echo Read the last error message above. You can also run diagnose_install.bat and share its output.
pause
exit /b 1
