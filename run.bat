@echo off
SETLOCAL EnableDelayedExpansion

:: --- Configuration ---
SET "VENV_DIR=.venv"
SET "SCRIPT_NAME=main.py"

echo Checking environment...

:: 1. Create Virtual Environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating virtual environment in %VENV_DIR%...
    py -m venv %VENV_DIR%
    if !errorlevel! neq 0 (
        echo Error: Failed to create virtual environment. 
        pause
        exit /b
    )
)

:: 2. Activate venv and check/install vrchatapi
echo Activating environment...
call "%VENV_DIR%\Scripts\activate"

:: We check if packages are installed by trying to show its info
pip show vrchatapi >nul 2>&1
if %errorlevel% neq 0 (
    echo vrchatapi not found. Installing...
    py -m pip install vrchatapi
) else (
    echo vrchatapi is already installed.
)

pip show icalendar >nul 2>&1
if %errorlevel% neq 0 (
    echo icalendar not found. Installing...
    py -m pip install icalendar
) else (
    echo icalendar is already installed.
)

:: 3. Run the script
echo.
echo Starting Tummy Funny Scripts...
echo ---------------------------------
python "%SCRIPT_NAME%"

:: Keep window open if the script crashes or finishes
echo.
echo ---------------------------------
echo Script finished.