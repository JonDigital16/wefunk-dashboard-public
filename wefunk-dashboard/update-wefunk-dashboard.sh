#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${WEFUNK_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

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


exec "$ROOT/bin/wefunk-dashboard"
