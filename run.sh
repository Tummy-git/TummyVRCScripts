#!/bin/bash

# --- Configuration ---
VENV_DIR=".venv"
SCRIPT_NAME="main.py"

echo "Checking environment..."

# 1. Create Virtual Environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        read -p "Press enter to exit..."
        exit 1
    fi
fi

# 2. Activate venv and check/install vrchatapi
echo "Activating environment..."
source "$VENV_DIR/bin/activate"

# Check if the vrchatapi is installed
if ! pip show vrchatapi > /dev/null 2>&1; then
    echo "vrchatapi not found. Installing..."
    python3 -m pip install vrchatapi
else
    echo "vrchatapi is already installed."
fi

# Check if the icalendar is installed
if ! pip show icalendar > /dev/null 2>&1; then
    echo "icalendar not found. Installing..."
    python3 -m pip install icalendar
else
    echo "icalendar is already installed."
fi

# 3. Run the script
echo ""
echo "Starting Tummy Funny Scripts..."
echo "---------------------------------"
python3 "$SCRIPT_NAME"

# Keep window open if the script crashes or finishes
echo ""
echo "---------------------------------"
echo "Script finished."