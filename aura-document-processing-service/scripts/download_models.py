"""Pre-descarga de modelos de HuggingFace en build-time.

Descarga el repositorio completo de cada modelo al cache de HuggingFace
(HF_HOME / ~/.cache/huggingface/hub) para que el arranque del contenedor
no dependa de la red ni de la descarga desde HuggingFace.

Los modelos se pasan como argumentos (separados por espacios o uno por arg).
Si la variable de entorno HF_TOKEN esta presente, se usa para evitar el
rate limit de descargas no autenticadas.
"""
import os
import sys

from huggingface_hub import snapshot_download


def download(models: list[str]) -> None:
    token = os.environ.get("HF_TOKEN") or None
    seen: set[str] = set()
    for raw in models:
        model = raw.strip()
        if not model or model in seen:
            continue
        seen.add(model)
        print(f"[download_models] Descargando {model} ...", flush=True)
        snapshot_download(repo_id=model, token=token)
        print(f"[download_models] OK {model}", flush=True)


if __name__ == "__main__":
    requested: list[str] = []
    for arg in sys.argv[1:]:
        requested.extend(arg.split())
    if not requested:
        print("[download_models] No se especificaron modelos; nada que hacer.", flush=True)
        sys.exit(0)
    download(requested)
