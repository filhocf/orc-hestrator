#!/usr/bin/env bash
# Build the SPA for the subpath deployment.
#
# Two flags are mandatory and were learned the hard way (20/out/2026):
#   --base=/orc/ui/    without it, index.html points to /assets/... -> blank page
#   VITE_API_BASE      without it, the client calls /api/... -> login silently fails
#                      (nginx serves the SPA for /orc/ui/api/* and the fetch gets HTML)
#
# Override for a different host: SPA_BASE=/ui/ VITE_API_BASE=/api ./scripts/build_ui.sh
set -euo pipefail

cd "$(dirname "$0")/../frontend"

SPA_BASE="${SPA_BASE:-/orc/ui/}"
API_BASE="${VITE_API_BASE:-/orc/api}"

VITE_API_BASE="$API_BASE" npm run build -- --base="$SPA_BASE"

echo "SPA built: base=$SPA_BASE api=$API_BASE"
echo "  dist/index.html -> $(grep -o 'src="[^"]*"' dist/index.html)"
echo "  publish with: tar czf - -C frontend/dist . | ssh <host> 'rm -rf ~/orc-ui && mkdir -p ~/orc-ui && tar xzf - -C ~/orc-ui'"
