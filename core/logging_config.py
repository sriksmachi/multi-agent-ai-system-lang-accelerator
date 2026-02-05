from __future__ import annotations
import logging

# Suppress verbose Azure SDK telemetry logging
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger