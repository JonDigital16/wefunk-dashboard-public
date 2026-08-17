#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${WEFUNK_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ROOT="$PROJECT"

# Load project-local configuration if present.
# Existing exported environment variables take precedence.
if [ -f "$ROOT/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"

    [[ "$key" == "$line" ]] && continue

    # Do not overwrite a value already supplied by the environment.
    if [[ -z "${(P)key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$ROOT/.env"
fi

APP_DIR="$PROJECT/wefunk-dashboard"
VENV="${WEFUNK_VENV:-$PROJECT/.venv}"
PORT="${WEFUNK_PORT:-8099}"
LOG_DIR="${WEFUNK_LOG_DIR:-$PROJECT/logs}"

mkdir -p "$LOG_DIR"
cd "$APP_DIR" || exit 1

exec "$VENV/bin/waitress-serve" \
  --listen="0.0.0.0:$PORT" \
  app:app
