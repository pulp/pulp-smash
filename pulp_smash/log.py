"""Pulpsmash logger module."""
# pragma: no cover
import functools
import logging
import os


@functools.lru_cache()
def get_logger(level):
    """Return the same logger instance for changed level."""
    logging.basicConfig(
        format=(
            "%(asctime)s,%(msecs)d %(levelname)-5s "
            "[%(filename)s:%(lineno)d - %(funcName)s] %(message)s"
        ),
        datefmt="%Y-%m-%d:%H:%M:%S",
    )
    logger = logging.getLogger("pulp_smash")
    logger.setLevel(getattr(logging, level, "DEBUG"))
    return logger


logger = get_logger(os.environ.get("PULP_SMASH_LOG_LEVEL", "ERROR"))
