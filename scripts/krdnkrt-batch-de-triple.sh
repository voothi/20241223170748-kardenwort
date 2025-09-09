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
echo "Running extraction in different modes..."

echo
echo "Triple word mode with GCS..."
# The --de-gcs flag enables German Compound Splitting for word mode.
"$PYTHON_PATH" "$SCRIPT" --language de --type word --mode triple --de-gcs --de-gcs-pos-tags "!VERB"

echo
echo "Triple sentence mode..."
# GCS flags are not applicable for sentence mode and will be ignored.
"$PYTHON_PATH" "$SCRIPT" --language de --type sentence --mode triple

echo
echo "All operations completed successfully."
exit 0