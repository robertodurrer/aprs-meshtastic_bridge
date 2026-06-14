#!/usr/bin/env python3
"""
Mesh↔APRS Gateway
Ponto de entrada principal — desenvolvido por etapas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config_loader import load as load_config
from modules.logger import get_logger

def main():
    cfg = load_config()
    log = get_logger("gateway", cfg)
    log.info("Mesh↔APRS Gateway iniciando...")
    log.info(f"Callsign do gateway: {cfg['gateway']['callsign']}")
    log.info("Etapa 1 OK — ambiente pronto")
    log.info("Próximo passo: implementar conexão Meshtastic (etapa 2)")

if __name__ == "__main__":
    main()
