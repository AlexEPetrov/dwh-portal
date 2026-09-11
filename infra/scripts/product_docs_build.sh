#!/usr/bin/env bash
# Full product-docs build: sync AsciiDoc component, then Antora static HTML.
# Registered in rules/policy.yaml as PRODUCT-DOCS-BUILD.
# Does not run AI enrich (that is on-request only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "product_docs_build: sync…"
python3 infra/scripts/product_docs_sync.py --mode sync

echo "product_docs_build: antora html…"
cd docs/generated/product-site
npx --yes -p @antora/cli@3.1.9 -p @antora/site-generator@3.1.9 antora generate antora-playbook.yml

INDEX="$ROOT/docs/generated/product-site/build/index.html"
test -f "$INDEX"
echo "product_docs_build: OK → $INDEX"
