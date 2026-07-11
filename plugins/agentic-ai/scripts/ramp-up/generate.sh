#!/usr/bin/env bash
#
# Wrapper script for PPTX generation.
# Checks for Python 3, installs pip dependencies, and runs md_to_pptx.py.
# If Python is not available, exits cleanly with a guidance message.
#
# Usage: bash generate.sh <input.md> <output.pptx>

set -euo pipefail

INPUT="$1"
OUTPUT="$2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Check for Python 3 ---
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    # Verify it's Python 3, not Python 2
    PY_VERSION=$(python --version 2>&1)
    if echo "$PY_VERSION" | grep -q "Python 3"; then
        PYTHON_CMD="python"
    fi
fi

# Fallback: check common Windows install locations (winget/python.org)
if [ -z "$PYTHON_CMD" ] && [ "$(uname -o 2>/dev/null)" = "Msys" ] || [ -n "${USERPROFILE:-}" ]; then
    WIN_HOME="${USERPROFILE:-$HOME}"
    WIN_HOME_UNIX="$(cygpath -u "$WIN_HOME" 2>/dev/null || echo "$WIN_HOME")"
    for py_dir in "$WIN_HOME_UNIX/AppData/Local/Programs/Python"/Python3*/python.exe; do
        if [ -x "$py_dir" ]; then
            PYTHON_CMD="$py_dir"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "SKIP_PPTX: Python 3 is not installed on this system."
    echo ""
    echo "The markdown file was created successfully, but PPTX generation requires Python 3."
    echo ""
    echo "To install Python 3:"
    echo "  Windows:     winget install Python.Python.3.12"
    echo "  macOS:       brew install python"
    echo "  Linux (apt): sudo apt install python3"
    echo "  Linux (dnf): sudo dnf install python3"
    echo ""
    echo "After installing, re-run the ramp-up skill to generate the PPTX."
    exit 0
fi

# --- Install dependencies if needed ---
$PYTHON_CMD -c "import pptx" 2>/dev/null || $PYTHON_CMD -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

# --- Generate PPTX ---
$PYTHON_CMD "$SCRIPT_DIR/md_to_pptx.py" --input "$INPUT" --output "$OUTPUT"
