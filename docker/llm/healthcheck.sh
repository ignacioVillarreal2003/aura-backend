#!/bin/sh
set -u

curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1 || exit 1

models="${OLLAMA_LLM_FACADE_MODEL_NAME:-}"
active_type=$(printf '%s' "${EMBEDDER_ACTIVE_TYPE:-}" | tr '[:upper:]' '[:lower:]')
if [ "$active_type" = "ollama" ] && [ -n "${EMBEDDER_OLLAMA_MODEL:-}" ]; then
	models="$models ${EMBEDDER_OLLAMA_MODEL}"
fi

for m in $models; do
	[ -n "$m" ] || continue
	ollama show "$m" >/dev/null 2>&1 || exit 1
done

exit 0
