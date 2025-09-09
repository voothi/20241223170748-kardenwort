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
echo "Dual word mode with GCS (excluding verbs)..."
"$PYTHON_PATH" "$SCRIPT" --language de --type word --mode dual --de-gcs --de-gcs-pos-tags "!VERB"

echo
echo "Dual sentence mode..."
# --de-gcs flags are ignored in 'sentence' mode by the main script, so they are not included here.
"$PYTHON_PATH" "$SCRIPT" --language de --type sentence --mode dual

echo
echo "All operations completed successfully."
exit 0