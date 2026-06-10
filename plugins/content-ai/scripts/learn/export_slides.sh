#!/usr/bin/env bash
#
# Wrapper for slide-image export.
# Detects Python 3, runs export_slides.py, and on failure best-effort installs the optional
# renderers (PyMuPDF for the LibreOffice path; pywin32 for the PowerPoint path on Windows)
# and retries once. Exits 0 even when export is skipped — image export must never block the
# rest of the learn skill.
#
# Usage: bash export_slides.sh <input.pptx> <output-dir> <prefix>

set -uo pipefail

INPUT="${1:?usage: export_slides.sh <input.pptx> <output-dir> <prefix>}"
OUTDIR="${2:?missing output-dir}"
PREFIX="${3:?missing prefix}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Check for Python 3 (same detection as generate.sh) ---
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PY_VERSION=$(python --version 2>&1)
    if echo "$PY_VERSION" | grep -q "Python 3"; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ] && { [ "$(uname -o 2>/dev/null)" = "Msys" ] || [ -n "${USERPROFILE:-}" ]; }; then
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
    echo "SKIP_EXPORT: Python 3 is not installed; cannot export slide images."
    echo "The LinkedIn article will still be created with image placeholders."
    exit 0
fi

run_export() {
    "$PYTHON_CMD" "$SCRIPT_DIR/export_slides.py" \
        --input "$INPUT" --output-dir "$OUTDIR" --prefix "$PREFIX"
}

OUT="$(run_export)"
printf '%s\n' "$OUT"
if printf '%s\n' "$OUT" | grep -q "EXPORTED"; then
    exit 0
fi

# First attempt produced no images — try to install optional renderers, then retry once.
echo "Attempting to install optional slide renderers (best effort)..."
"$PYTHON_CMD" -m pip install -q pymupdf >/dev/null 2>&1 || true
case "$(uname -s 2>/dev/null)" in
    MINGW* | MSYS* | CYGWIN* | Windows*) "$PYTHON_CMD" -m pip install -q pywin32 >/dev/null 2>&1 || true ;;
    *) [ -n "${USERPROFILE:-}" ] && "$PYTHON_CMD" -m pip install -q pywin32 >/dev/null 2>&1 || true ;;
esac

run_export
exit 0
