# Developer convenience targets for aura-document-processing-service.

PY_IMAGE ?= python:3.13-slim

.PHONY: lock lock-verify

## Regenerate the pinned, hash-locked requirements/*.txt from requirements/*.in.
## Runs inside the runtime base image so pins/hashes match the deploy platform.
lock:
	docker run --rm -v "$(CURDIR):/work" -w /work $(PY_IMAGE) bash scripts/compile_requirements.sh

## Verify the CPU lockfile resolves cleanly (dry-run, no app code installed).
lock-verify:
	docker run --rm -v "$(CURDIR):/work" -w /work $(PY_IMAGE) \
		bash -c "pip install --no-cache-dir --dry-run -r requirements/requirements.txt"
