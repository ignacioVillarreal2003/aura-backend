#!/bin/sh
set -eu

_maybe_pull_then_serve() {
	if [ "${1:-}" != "serve" ]; then
		return 0
	fi
	if ! command -v curl >/dev/null 2>&1; then
		return 0
	fi

	ollama serve >/dev/null 2>&1 &
	OLLAMA_PID=$!
	i=1
	while [ "$i" -le 90 ]; do
		if curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
			break
		fi
		sleep 1
		i=$((i + 1))
	done
	if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
		kill "$OLLAMA_PID" 2>/dev/null || true
		wait "$OLLAMA_PID" 2>/dev/null || true
		return 0
	fi

	raw="${OLLAMA_LLM_FACADE_MODEL_NAME:-}"
	active_type=$(printf '%s' "${EMBEDDER_ACTIVE_TYPE:-}" | tr '[:upper:]' '[:lower:]')
	if [ "$active_type" = "ollama" ] && [ -n "${EMBEDDER_OLLAMA_MODEL:-}" ]; then
		raw="$raw ${EMBEDDER_OLLAMA_MODEL}"
	fi

	seen=""
	for m in $raw; do
		[ -n "$m" ] || continue
		case " $seen " in *" $m "*) continue ;;
		esac
		ollama pull "$m"
		seen="$seen $m"
	done

	kill "$OLLAMA_PID" 2>/dev/null || true
	wait "$OLLAMA_PID" 2>/dev/null || true
}

_maybe_pull_then_serve "$@"
exec ollama "$@"
