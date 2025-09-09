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

# Run script
echo "Running word extraction for a single German text..."

echo
echo "Single word mode with GCS (excluding verbs)..."
"$PYTHON_PATH" "$SCRIPT" --language de --type word --mode single --de-gcs --de-gcs-pos-tags "!VERB"

echo
echo "All operations completed successfully."
exit 0