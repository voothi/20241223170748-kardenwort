#!/bin/bash
set -e

# --- Universal startup block ---
WORKSPACE=$(cd "$(dirname "$0")/.." && pwd)
RUNNER_SCRIPT="kardenwort-runner.py"

if ! command -v python3 &> /dev/null; then
    echo "ERROR: 'python3' command not found. Please ensure it is installed and in your PATH." >&2
    exit 1
fi

PYTHON_PATH=$(python3 "$WORKSPACE/$RUNNER_SCRIPT" --get-python-path)
if [ $? -ne 0 ] || [ ! -f "$PYTHON_PATH" ]; then
    echo "ERROR: Failed to get Python path from config.ini. See script output above for details." >&2
    exit 1
fi

cd "$WORKSPACE" || { echo "ERROR: Failed to change directory to $WORKSPACE" >&2; exit 1; }
# --- End of universal block ---


echo "Running word extraction for a single German text..."

echo
echo "Single word mode with GCS (excluding verbs)..."
"$PYTHON_PATH" "$RUNNER_SCRIPT" --language de --type word --mode single --de-gcs --de-gcs-pos-tags "!VERB"

echo
echo "All operations completed successfully."
exit 0