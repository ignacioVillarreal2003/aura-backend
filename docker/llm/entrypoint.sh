#!/bin/sh
set -eu

PULL_RETRIES="${OLLAMA_PULL_RETRIES:-3}"

_log() {
	echo "[entrypoint] $*"
}

_required_models() {
	raw="${OLLAMA_LLM_FACADE_MODEL_NAME:-}"
	active_type=$(printf '%s' "${EMBEDDER_ACTIVE_TYPE:-}" | tr '[:upper:]' '[:lower:]')
	if [ "$active_type" = "ollama" ] && [ -n "${EMBEDDER_OLLAMA_MODEL:-}" ]; then
		raw="$raw ${EMBEDDER_OLLAMA_MODEL}"
	fi
	printf '%s' "$raw"
}

_model_present() {
	ollama show "$1" >/dev/null 2>&1
}

_pull_with_retries() {
	model="$1"
	attempt=1
	while [ "$attempt" -le "$PULL_RETRIES" ]; do
		if ollama pull "$model"; then
			return 0
		fi
		_log "Pull failed for '$model' (attempt $attempt/$PULL_RETRIES)."
		[ "$attempt" -lt "$PULL_RETRIES" ] && sleep $((attempt * 10))
		attempt=$((attempt + 1))
	done
	return 1
}

_ensure_models() {
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
		_log "Ollama API did not come up for the pre-pull phase; continuing to serve."
		kill "$OLLAMA_PID" 2>/dev/null || true
		wait "$OLLAMA_PID" 2>/dev/null || true
		return 0
	fi

	missing=""
	seen=""
	for m in $(_required_models); do
		[ -n "$m" ] || continue
		case " $seen " in *" $m "*) continue ;;
		esac
		seen="$seen $m"
		if _model_present "$m"; then
			_log "Model '$m' is already available locally; skipping pull."
			continue
		fi
		_log "Model '$m' is missing locally; pulling..."
		if ! _pull_with_retries "$m"; then
			missing="$missing $m"
		fi
	done

	kill "$OLLAMA_PID" 2>/dev/null || true
	wait "$OLLAMA_PID" 2>/dev/null || true

	if [ -n "$missing" ]; then
		_log "ERROR: could not provision required model(s):$missing"
		_log "Check the model names and network connectivity; exiting so the container restarts and retries."
		exit 1
	fi
}

_ensure_models "$@"
exec ollama "$@"
