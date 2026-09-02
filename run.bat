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

:: We check if packages are installed by trying to show its info
for %%P in (vrchatapi icalendar rich) do (
    pip show %%P >nul 2>&1
    if !errorlevel! neq 0 (
        echo %%P not found. Installing...
        py -m pip install %%P
    ) else (
        echo %%P is already installed.
    )
)

:: 3. Run the script
echo.
echo Starting VRChat Toolbox...
echo ---------------------------------
python "%SCRIPT_NAME%"

:: Keep window open if the script crashes or finishes
echo.
echo ---------------------------------
echo Script finished.