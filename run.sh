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
        exit 1
    fi
fi

# 2. Activate venv and check/install dependencies
echo "Activating environment..."
source "$VENV_DIR/bin/activate"

# Dependency checker loop
for pkg in vrchatapi icalendar rich; do
    if ! pip show $pkg > /dev/null 2>&1; then
        echo "$pkg not found. Installing..."
        python3 -m pip install $pkg
    else
        echo "$pkg is already installed."
    fi
done

# 3. Run the script, forwarding any arguments (like --run)
echo ""
echo "Starting VRChat Toolbox..."
echo "---------------------------------"
python3 "$SCRIPT_NAME" "$@"

echo ""
echo "---------------------------------"
echo "Script finished."