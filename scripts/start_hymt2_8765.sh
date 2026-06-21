#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LLAMA_SERVER="${LLAMA_SERVER:-$PROJECT_ROOT/bin/llama-server}"
MODEL="${HYMT2_MODEL:-$PROJECT_ROOT/_model_cache/Hy-MT2-1.8B-Q6_K.gguf}"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server is not executable: $LLAMA_SERVER" >&2
  echo "Set LLAMA_SERVER to your llama.cpp server executable." >&2
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  echo "Hy-MT2 model was not found: $MODEL" >&2
  echo "Set HYMT2_MODEL to your GGUF model file." >&2
  exit 1
fi

exec "$LLAMA_SERVER" \
  -m "$MODEL" \
  --jinja \
  -c 8192 \
  -np 1 \
  --cache-ram 0 \
  --no-cache-idle-slots \
  -ngl 99 \
  --host 127.0.0.1 \
  --port "${HYMT2_PORT:-8765}" \
  --temp 0.7 \
  --top-p 0.6 \
  --top-k 20 \
  --repeat-penalty 1.05
