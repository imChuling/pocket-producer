#!/usr/bin/env bash
set -euo pipefail

# Deterministic LBD PDF build.
# Copies sources to a clean /tmp directory (avoids iCloud interference),
# builds with tectonic, asserts page count, copies result back.
#
# iCloud resilience: files that are 0 bytes or hang on copy are treated
# as evicted. Template files (ismir.sty, cc_by.pdf) are re-downloaded
# from the ISMIR GitHub repo; IEEEtran.bst is left to tectonic's bundle.
# Content files (lbd.tex, references.bib) fall back to ~/dev/ismir-backup/.
#
# Usage:
#   ./docs/ismir2026/build.sh              # full build with number check
#   SKIP_CHECK=1 ./docs/ismir2026/build.sh # skip number check

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$HOME/dev/ismir-backup"
BUILD_DIR="/tmp/lbd-build"
OUT_PDF="$BUILD_DIR/lbd.pdf"
FINAL_PDF="$SCRIPT_DIR/lbd.pdf"
ISMIR_GITHUB="https://raw.githubusercontent.com/ismir/paper_templates/master/2026/latex"

echo "=== LBD Build ==="

# macOS has no GNU `timeout` by default; degrade to running the command
# directly. (The timeout only guards against iCloud-evicted files hanging.)
run_timeout() {
    local secs="$1"; shift
    if command -v timeout &>/dev/null; then
        timeout "$secs" "$@"
    else
        "$@"
    fi
}

# 1. Number check
if [ "${SKIP_CHECK:-}" = "1" ]; then
    echo "[1/5] Skipping number check (SKIP_CHECK=1)"
elif command -v python3 &>/dev/null; then
    echo "[1/5] Running number consistency check..."
    if run_timeout 30 python3 "$REPO_ROOT/research/check_paper_numbers.py" 2>/dev/null; then
        echo "  Numbers OK."
    else
        echo "  ABORT: number check failed or timed out."
        echo "  Fix the mismatch, or rerun with SKIP_CHECK=1 to override."
        exit 1
    fi
else
    echo "[1/5] Skipping number check (python3 not found)"
fi

# 2. Stage files
echo "[2/5] Staging to $BUILD_DIR..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/assets"

# Try to copy a file with a timeout; fall back to backup dir, then skip.
safe_copy() {
    local src="$1" dst="$2" name="$(basename "$1")"
    if run_timeout 3 cp "$src" "$dst" 2>/dev/null; then
        return 0
    fi
    if [ -d "$BACKUP_DIR" ] && [ -s "$BACKUP_DIR/$name" ]; then
        cp "$BACKUP_DIR/$name" "$dst"
        echo "  $name: from backup"
        return 0
    fi
    return 1
}

# Content files (must exist)
for f in lbd.tex references.bib; do
    if ! safe_copy "$SCRIPT_DIR/$f" "$BUILD_DIR/$f"; then
        echo "  ABORT: $f unavailable in source or backup."
        exit 1
    fi
done

# cite.sty
safe_copy "$SCRIPT_DIR/cite.sty" "$BUILD_DIR/cite.sty" || {
    echo "  cite.sty: unavailable, trying backup"
    [ -s "$BACKUP_DIR/cite.sty" ] && cp "$BACKUP_DIR/cite.sty" "$BUILD_DIR/"
}

# Template files: download if evicted
for f in ismir.sty cc_by.pdf; do
    if ! safe_copy "$SCRIPT_DIR/$f" "$BUILD_DIR/$f"; then
        echo "  $f: downloading from ISMIR GitHub..."
        curl -sL "$ISMIR_GITHUB/$f" -o "$BUILD_DIR/$f"
        [ -s "$BUILD_DIR/$f" ] || { echo "  ABORT: failed to download $f"; exit 1; }
    fi
done

# IEEEtran.bst: let tectonic handle it (bundled)

# Assets
for f in "$SCRIPT_DIR/assets/"*.tex "$SCRIPT_DIR/assets/"*.pdf "$SCRIPT_DIR/assets/"*.png; do
    [ -f "$f" ] || continue
    name="$(basename "$f")"
    if ! run_timeout 3 cp "$f" "$BUILD_DIR/assets/$name" 2>/dev/null; then
        if [ -d "$BACKUP_DIR/assets" ] && [ -s "$BACKUP_DIR/assets/$name" ]; then
            cp "$BACKUP_DIR/assets/$name" "$BUILD_DIR/assets/$name"
            echo "  assets/$name: from backup"
        else
            echo "  WARNING: assets/$name unavailable"
        fi
    fi
done

echo "  Staged $(ls "$BUILD_DIR" | wc -l | tr -d ' ') files + $(ls "$BUILD_DIR/assets" | wc -l | tr -d ' ') assets"

# 3. Build
echo "[3/5] Building with tectonic..."
cd "$BUILD_DIR"
tectonic lbd.tex 2>&1

if [ ! -s "$OUT_PDF" ]; then
    echo "  ABORT: tectonic produced no output."
    exit 1
fi

# 4. Assertions
echo "[4/5] Checking constraints..."
SIZE=$(stat -f%z "$OUT_PDF" 2>/dev/null || stat -c%s "$OUT_PDF" 2>/dev/null || echo 0)
echo "  File size: ${SIZE} bytes"

if [ "$SIZE" -lt 10000 ]; then
    echo "  WARNING: PDF suspiciously small (< 10KB)"
fi

# Page count: LBD format is 2 content pages + 1 references = exactly 3.
PAGES=""
if command -v pdfinfo &>/dev/null; then
    PAGES=$(pdfinfo "$OUT_PDF" 2>/dev/null | awk '/^Pages:/ {print $2}')
elif command -v python3 &>/dev/null; then
    PAGES=$(python3 - "$OUT_PDF" <<'PYEOF'
import re, sys
data = open(sys.argv[1], "rb").read()
m = re.search(rb"/Type\s*/Pages.*?/Count\s+(\d+)", data, re.S)
print(m.group(1).decode() if m else "")
PYEOF
)
fi
if [ -n "$PAGES" ]; then
    echo "  Page count: $PAGES"
    if [ "$PAGES" != "3" ]; then
        echo "  ABORT: expected exactly 3 pages (2 content + 1 references), got $PAGES."
        exit 1
    fi
else
    echo "  WARNING: could not determine page count."
fi

# 5. Copy back
echo "[5/5] Copying to $FINAL_PDF..."
cp "$OUT_PDF" "$FINAL_PDF"

echo "=== Done: $FINAL_PDF ==="
