#!/usr/bin/env bash
# Everything that can be checked without a cluster. Run before every apply.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> manifest and config invariants"
python3 -m pytest tests/ -q

echo "==> gate self-check (the gate gates itself)"
python3 gate/run_gate.py --target . --report QUALITY_REPORT.md

if command -v kustomize >/dev/null; then
  echo "==> kustomize build"
  kustomize build deploy/overlays/local > /dev/null && echo "    overlay renders"
else
  echo "==> kustomize not installed — overlay render NOT verified" >&2
fi

if command -v kubectl >/dev/null; then
  echo "==> server-side dry run"
  kubectl apply -k deploy/overlays/local --dry-run=server
else
  echo "==> kubectl not installed — dry run NOT performed" >&2
fi
