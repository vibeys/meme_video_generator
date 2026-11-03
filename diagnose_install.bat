@echo off
setlocal
cd /d "%~dp0"
title Automatic Meme Video Generator - Diagnostics

echo ================================================
echo   Automatic Meme Video Generator Diagnostics
echo ================================================
echo.

where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version
) else (
    python --version
)

echo.
echo Checking virtual environment...
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe --version
    .venv\Scripts\python.exe -m pip --version
    echo.
    echo Checking required imports...
    .venv\Scripts\python.exe -c "import praw, dotenv, pyttsx3, edge_tts, cv2, PIL, imageio_ffmpeg; print('All required imports succeeded.'); print('FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"
) else (
    echo .venv\Scripts\python.exe was not found. The virtual environment has not been created yet.
)

echo.
echo Checking project folders...
if exist "assets\gameplay" (echo assets\gameplay exists.) else (echo assets\gameplay is missing.)
if exist "output" (echo output exists.) else (echo output is missing.)
if exist ".env" (echo .env exists.) else (echo .env is not present yet. This is normal before installation.)

echo.
echo Copy the complete output above when reporting an installation problem.
pause
