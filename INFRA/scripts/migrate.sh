#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CAT AI — Database migration runner
# Usage:
#   ./scripts/migrate.sh              # apply all pending migrations
#   ./scripts/migrate.sh downgrade -1 # roll back one revision
#   ./scripts/migrate.sh revision --autogenerate -m "add index"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$SCRIPT_DIR/../apps/api"
ALEMBIC_INI="$API_DIR/db/migrations/alembic.ini"

# Default command: upgrade to head
COMMAND="${1:-upgrade}"
ARGS="${@:2:-head}"

if [ "$COMMAND" = "upgrade" ] && [ $# -eq 1 ]; then
    ARGS="head"
fi

echo "📦  Running: alembic -c $ALEMBIC_INI $COMMAND $ARGS"
cd "$API_DIR"
python -m alembic -c db/migrations/alembic.ini "$COMMAND" $ARGS

echo "✅  Migration complete"