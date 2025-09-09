#!/bin/bash
set -e

# Set paths - PLEASE UPDATE THESE FOR YOUR SYSTEM
PYTHON_PATH="/path/to/voothi/20250825231214-spacy-env/bin/python"
WORKSPACE="/path/to/voothi/20241223170748-kardenwort-kern"
SCRIPT="krdnkrt-krn-runner.py"

# Verify Python exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "ERROR: Python executable not found at: $PYTHON_PATH" >&2
    exit 1
fi

# Change to workspace directory
cd "$WORKSPACE" || { echo "ERROR: Failed to change directory to $WORKSPACE" >&2; exit 1; }

# Run script with different modes
echo "Running extraction for English in dual mode..."

echo
echo "Dual word mode..."
"$PYTHON_PATH" "$SCRIPT" --language en --type word --mode dual

echo
echo "Dual sentence mode..."
"$PYTHON_PATH" "$SCRIPT" --language en --type sentence --mode dual

echo
echo "All operations completed successfully."
exit 0