import logging

from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


class GpuUnavailableError(RuntimeError):
    pass


def verify_gpu_availability() -> None:
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
