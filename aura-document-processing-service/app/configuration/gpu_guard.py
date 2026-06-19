import logging

from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


class GpuUnavailableError(RuntimeError):
    """Raised when REQUIRE_GPU is set but no CUDA device is reachable."""


def verify_gpu_availability() -> None:
    """Fail fast when a GPU deployment cannot actually reach a CUDA device.

    The PyTorch CUDA wheels silently fall back to CPU when the NVIDIA runtime is
    missing (no ``--gpus all``, no nvidia-container-toolkit, no host driver). On a GPU
    deployment that means the service boots "fine" but runs inference on CPU, orders
    of magnitude slower. When ``REQUIRE_GPU`` is true we refuse to start instead.

    No-op when ``REQUIRE_GPU`` is false (CPU deployments), so torch is only imported
    when a GPU is actually expected.
    """
    if not environment_variables.require_gpu:
        return

    import torch

    if not torch.cuda.is_available():
        raise GpuUnavailableError(
            "REQUIRE_GPU is true but torch.cuda.is_available() is False. The CUDA "
            "runtime is not reachable: start the container with the NVIDIA toolkit "
            "(e.g. `--gpus all`) and a host driver, or set REQUIRE_GPU=false to run on CPU."
        )

    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0) if device_count else "unknown"
    logger.info(
        "CUDA verified: %d device(s) available, primary='%s'.",
        device_count,
        device_name,
    )
