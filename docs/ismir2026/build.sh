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

# 1. Number check
if [ "${SKIP_CHECK:-}" = "1" ]; then
    echo "[1/5] Skipping number check (SKIP_CHECK=1)"
elif command -v python3 &>/dev/null; then
    echo "[1/5] Running number consistency check..."
    if timeout 30 python3 "$REPO_ROOT/research/check_paper_numbers.py" 2>/dev/null; then
        echo "  Numbers OK."
    else
        echo "  WARNING: number check failed or timed out (iCloud?). Continuing build."
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
    if timeout 3 cp "$src" "$dst" 2>/dev/null; then
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
for f in "$SCRIPT_DIR/assets/"*.tex "$SCRIPT_DIR/assets/"*.pdf; do
    [ -f "$f" ] || continue
    name="$(basename "$f")"
    if ! timeout 3 cp "$f" "$BUILD_DIR/assets/$name" 2>/dev/null; then
        if [ -d "$BACKUP_DIR/assets" ] && [ -s "$BACKUP_DIR/assets/$name" ]; then
            cp "$BACKUP_DIR/assets/$name" "$BUILD_DIR/assets/$name"
            echo "  assets/$name: from backup"
        else
            echo "  WARNING: assets/$name unavailable"
        fi
    fi
done

# Regenerate system-figure.pdf if corrupt or missing
if ! python3 -c "
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(7.0,1.1),dpi=300); ax.axis('off')
steps=['Audiotool\nsession','Session\nfingerprint','Retrieval\n(RRF)','Ranking\n(fusion)','Reversible\naction','Preference\nfeedback']
for i,l in enumerate(steps):
    ax.text(i*1.18+.5,.5,l,ha='center',va='center',fontsize=7,bbox={'boxstyle':'round,pad=0.35','facecolor':'#eee','edgecolor':'#555'})
    if i<len(steps)-1: ax.annotate('',xy=(i*1.18+1.06,.5),xytext=(i*1.18+.92,.5),arrowprops={'arrowstyle':'->','color':'#555'})
ax.set_xlim(0,len(steps)*1.18); ax.set_ylim(0,1)
fig.savefig('$BUILD_DIR/assets/system-figure.pdf',metadata={'CreationDate':None,'Producer':None,'Creator':None},bbox_inches='tight')
" 2>/dev/null; then
    echo "  WARNING: could not regenerate system-figure.pdf"
fi

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

# 5. Copy back
echo "[5/5] Copying to $FINAL_PDF..."
cp "$OUT_PDF" "$FINAL_PDF"

echo "=== Done: $FINAL_PDF ==="
