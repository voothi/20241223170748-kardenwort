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

# Run script for a single English text file
echo "Running extraction for a single English text..."

echo
echo "Single word mode..."
"$PYTHON_PATH" "$SCRIPT" --language en --type word --mode single

# The 'sentence' mode requires at least two files ('dual' or 'triple' mode) and cannot be run in 'single' mode.

echo
echo "All operations completed successfully."
exit 0