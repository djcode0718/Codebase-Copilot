import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Configure and return a logger."""
    logger = logging.getLogger(name)
    # Avoid duplicate emission to root handlers that may still use cp1252 streams.
    logger.propagate = False
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        # On Windows terminals, avoid crashing when non-ASCII slips into logs.
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
