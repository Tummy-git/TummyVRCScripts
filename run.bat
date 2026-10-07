@echo off
SETLOCAL EnableDelayedExpansion

:: Force Terminal and Python to use UTF-8
chcp 65001 >nul
SET "PYTHONUTF8=1"

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

:: 2. Activate venv and check/install dependencies
echo Activating environment...
call "%VENV_DIR%\Scripts\activate"

:: Install/update dependencies to the versions pinned in requirements.txt
python -m pip install -q -r requirements.txt

:: 3. Run the script, forwarding any arguments (like --run)
echo.
echo Starting VRChat Toolbox...
echo ---------------------------------
python "%SCRIPT_NAME%" %*

:: Keep window open if the script crashes or finishes (skipped for --run so scheduled runs don't hang)
echo.
echo ---------------------------------
echo Script finished.
if "%~1"=="" pause