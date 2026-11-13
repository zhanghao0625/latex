#!/bin/sh
# Copyright (c) 2026-2027 zh
# 内容：编译现有论文稿件，PDF 输出到论文目录，辅助产物存放于 tmp 目录。
# 用法：sh traction_compliance/build.sh
set -eu

PAPER_DIR=$(cd "$(dirname "$0")" && pwd)
BUILD_DIR="${PAPER_DIR}/tmp"

echo "Paper directory: ${PAPER_DIR}"
echo "Build directory: ${BUILD_DIR}"
if [ ! -f "${PAPER_DIR}/main.tex" ]; then
  echo "ERROR: Manuscript not found: ${PAPER_DIR}/main.tex" >&2
  exit 1
fi

if command -v latexmk >/dev/null 2>&1 && command -v xelatex >/dev/null 2>&1; then
  COMPILER=latexmk
elif command -v tectonic >/dev/null 2>&1; then
  COMPILER=tectonic
else
  echo "ERROR: Install XeLaTeX with latexmk, or Tectonic, and add it to PATH." >&2
  exit 1
fi

mkdir -p "${BUILD_DIR}"
cd "${PAPER_DIR}"
for manuscript in main.tex main_cn.tex; do
  if [ ! -f "${manuscript}" ]; then
    continue
  fi
  echo "Building manuscript: ${manuscript}"
  if [ "${COMPILER}" = latexmk ]; then
    latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -outdir="${BUILD_DIR}" "${manuscript}"
  else
    tectonic --bundle "${TECTONIC_BUNDLE:-https://data1.fullyjustified.net/tlextras-2022.0r0.tar}" --keep-logs --keep-intermediates --outdir "${BUILD_DIR}" "${manuscript}"
  fi
  pdf_name="${manuscript%.tex}.pdf"
  mv "${BUILD_DIR}/${pdf_name}" "${PAPER_DIR}/${pdf_name}"
  echo "Built PDF: ${PAPER_DIR}/${pdf_name}"
done
echo "Build completed."
