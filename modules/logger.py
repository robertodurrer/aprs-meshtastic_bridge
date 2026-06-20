"""Logger centralizado do gateway."""
import logging
import logging.handlers
import sys
from pathlib import Path

def get_logger(name: str, cfg: dict = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Configuração padrão
    level = logging.INFO
    console_enabled = True
    max_size_mb = 10
    backup_count = 5
    
    if cfg and "logging" in cfg:
        log_cfg = cfg["logging"]
        level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
        console_enabled = log_cfg.get("console", True)
        max_size_mb = log_cfg.get("max_size_mb", 10)
        backup_count = log_cfg.get("backup_count", 5)

    # Formato mais detalhado
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)8s] %(name)12s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    if console_enabled:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # Arquivo rotativo
    if cfg and "logging" in cfg and "file" in cfg["logging"]:
        try:
            log_path = Path(__file__).parent.parent / cfg["logging"]["file"]
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception as e:
            print(f"Erro ao configurar log em arquivo: {e}", file=sys.stderr)

    logger.setLevel(level)
    return logger
