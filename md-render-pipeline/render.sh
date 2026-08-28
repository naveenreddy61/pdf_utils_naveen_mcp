#!/usr/bin/env bash
# render.sh — Markdown to PDF with Pandoc + Typst.
#
# Usage: render.sh <input.md> <output.pdf>
#
# Steps:
#   1. Copy the input to a temp file. The input file is never changed.
#   2. Remove "citeturn..." citation artifacts and private-use Unicode.
#   3. If node + katex are available, apply safe math auto-fixes
#      (empty \sqrt{} only; the copy already has no private-use glyphs).
#   4. Run pandoc with the Typst engine and the style assets in this
#      directory.
#
# Necessary tools: pandoc (>= 3.x), typst (>= 0.12). Optional: node.

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $0 <input.md> <output.pdf>" >&2
  exit 2
fi

INPUT=$1
OUTPUT=$2
PIPE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ ! -f "$INPUT" ]; then
  echo "error: input file not found: $INPUT" >&2
  exit 1
fi

command -v pandoc >/dev/null || { echo "error: pandoc not found" >&2; exit 1; }
command -v typst  >/dev/null || { echo "error: typst not found"  >&2; exit 1; }

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
WORK="$TMP_DIR/input.md"

# Step 2: strip citation artifacts and private-use Unicode glyphs.
perl -CSD -pe '
  s/[\x{E000}-\x{F8FF}]//g;
  s/cite(?:turn\d+[a-z]+\d+)+//g;
' "$INPUT" > "$WORK"

# Step 3: safe math auto-fixes (optional).
if command -v node >/dev/null && [ -d "$PIPE_DIR/node_modules/katex" ]; then
  node "$PIPE_DIR/mdlint-cli.mjs" "$WORK" --fix --fix=empty-sqrt \
    > "$TMP_DIR/mdlint.log" 2>&1 \
    || { echo "warning: mdlint failed, see log:" >&2; cat "$TMP_DIR/mdlint.log" >&2; }
else
  echo "note: node or katex not available — math auto-fix skipped" >&2
fi

# Step 4: render.
pandoc "$WORK" \
  --from=gfm+pipe_tables+footnotes+smart+tex_math_dollars \
  --lua-filter="$PIPE_DIR/table-widths.lua" \
  --lua-filter="$PIPE_DIR/bar-to-overline.lua" \
  --pdf-engine=typst \
  --metadata-file="$PIPE_DIR/typst-meta.yaml" \
  -V fontsize=11pt \
  -V mainfont="New Computer Modern" \
  -V mathfont="New Computer Modern Math" \
  -V linestretch=1.25 \
  -H "$PIPE_DIR/typst-header.typ" \
  -o "$OUTPUT"

echo "wrote $OUTPUT"
