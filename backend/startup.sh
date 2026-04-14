#!/bin/bash
set -e

# Always execute relative to this script's directory.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Azure App Service provides PORT. Default to 8000 for local fallback.
PORT_TO_USE="${PORT:-8000}"

pip install --no-cache-dir -r requirements.txt
exec gunicorn --bind="0.0.0.0:${PORT_TO_USE}" --timeout 180 app:app