#!/usr/bin/env bash
#
# Compiles the human-edited *.in source files into fully-pinned *.txt lockfiles
# for reproducible builds (audit A-1): every direct AND transitive package is
# pinned to an exact == version.
#
# This MUST run inside the runtime base image (python:3.13-slim) so the resolved
# pins match the deployment platform exactly. Compiling on a developer host
# (different OS/arch/Python) would emit platform-specific pins that break the
# Linux Docker build.
#
# NOTE on hashes: --generate-hashes is intentionally NOT used. pip-tools must
# download every artifact to hash it, and the PyTorch wheels (CPU hundreds of MB,
# CUDA several GB) make that impractical and flaky in CI. Exact == pins already
# deliver reproducible builds; hash pinning can be layered on later for the
# non-torch subset if stricter supply-chain guarantees are required.
#
# Usage (from the repository root):
#   docker run --rm -v "$PWD:/work" -w /work python:3.13-slim bash scripts/compile_requirements.sh
# or simply:
#   make lock
#
set -euo pipefail

REQ_DIR="$(cd "$(dirname "$0")/../requirements" && pwd)"
cd "$REQ_DIR"

# Give pip generous network timeouts/retries for the large PyTorch index.
export PIP_DEFAULT_TIMEOUT=120
export PIP_RETRIES=5

echo ">> Installing pip-tools"
pip install --no-cache-dir "pip-tools>=7.4.0" >/dev/null

# --emit-index-url  : keep the PyTorch extra index in the output so torch resolves.
# --no-strip-extras : keep behaviour explicit and stable across pip-tools versions.
COMMON_ARGS=(--emit-index-url --no-strip-extras --quiet)

echo ">> Locking requirements.txt (CPU)"
pip-compile "${COMMON_ARGS[@]}" --output-file requirements.txt requirements.in

echo ">> Locking requirements.gpu.txt (CUDA)"
pip-compile "${COMMON_ARGS[@]}" --output-file requirements.gpu.txt requirements.gpu.in

# Compiled AFTER requirements.txt because requirements.test.in constrains against it.
echo ">> Locking requirements.test.txt (test/dev)"
pip-compile "${COMMON_ARGS[@]}" --output-file requirements.test.txt requirements.test.in

echo ">> Lockfiles regenerated successfully."
