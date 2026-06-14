"""Logger centralizado do gateway."""
import logging
import logging.handlers
from pathlib import Path

def get_logger(name: str, cfg: dict = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = logging.INFO
    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Arquivo rotativo
    if cfg:
        log_path = Path(__file__).parent.parent / cfg["logging"]["file"]
        log_path.parent.mkdir(exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=cfg["logging"]["max_bytes"],
            backupCount=cfg["logging"]["backup_count"]
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        level = getattr(logging, cfg["logging"]["level"], logging.INFO)

    logger.setLevel(level)
    return logger
