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


echo "Running extraction for English in dual mode..."

echo
echo "Dual word mode..."
"$PYTHON_PATH" "$RUNNER_SCRIPT" --language en --type word --mode dual

echo
echo "Dual sentence mode..."
"$PYTHON_PATH" "$RUNNER_SCRIPT" --language en --type sentence --mode dual

echo
echo "All operations completed successfully."
exit 0