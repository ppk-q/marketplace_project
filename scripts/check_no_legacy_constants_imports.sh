#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PATTERN='^\s*(from\s+app\.constants\s+import|import\s+app\.constants(\s|$))'
OUTPUT_FILE="$(mktemp)"
trap 'rm -f "${OUTPUT_FILE}"' EXIT

if rg --line-number --glob '*.py' "${PATTERN}" app tests worker alembic >"${OUTPUT_FILE}"; then
  echo "ERROR: legacy imports from app.constants are forbidden."
  echo "Use app.constants_auth/app.constants_blog/app.constants_media/app.constants_api/app.constants_system."
  echo
  cat "${OUTPUT_FILE}"
  exit 1
fi

echo "OK: no legacy imports from app.constants found."
