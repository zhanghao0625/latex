#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build output/pdf
if command -v tectonic >/dev/null 2>&1; then
  tectonic --bundle "${TECTONIC_BUNDLE:-https://data1.fullyjustified.net/tlextras-2022.0r0.tar}" --keep-logs --keep-intermediates --outdir build main.tex
elif command -v latexmk >/dev/null 2>&1; then
  latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build main.tex
else
  echo 'Install Tectonic or XeLaTeX with latexmk, then run ./build.sh.' >&2
  exit 1
fi
cp build/main.pdf output/pdf/traction_compliance_review.pdf
