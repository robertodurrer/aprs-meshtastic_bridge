#!/usr/bin/env python3
"""
Mesh↔APRS Gateway — main.py
Etapa 4: posição Meshtastic → APRS-IS
"""
import sys
import time
import signal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config_loader import load as load_config
from modules.logger import get_logger
from modules.database import Database
from modules.meshtastic_interface import MeshtasticInterface
from modules.aprs_is_connection import APRSISConnection
from modules.position_handler import PositionHandler

log = get_logger("gateway")
cfg = load_config()

# Componentes globais
db      = Database(cfg)
aprs_is = APRSISConnection(cfg)
mesh    = MeshtasticInterface(cfg)
pos_hdl = PositionHandler(db, aprs_is)

def on_position(payload):
    pos_hdl.handle(payload)

def on_message(payload):
    # Etapa 5
    log.info(f"MSG recebida (etapa 5): {payload['from_id']}: {payload['text'][:60]}")

def shutdown(sig, frame):
    log.info("Encerrando gateway...")
    mesh.stop()
    aprs_is.stop()
    sys.exit(0)

def main():
    log.info("═══════════════════════════════════════")
    log.info("  Mesh↔APRS Gateway  —  iniciando")
    log.info(f"  Callsign: {cfg['gateway']['callsign']}")
    log.info("═══════════════════════════════════════")

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Inicia conexão APRS-IS
    aprs_is.start()
    time.sleep(2)  # aguarda login

    # Registra callbacks e inicia Meshtastic
    mesh.on_position(on_position)
    mesh.on_message(on_message)
    mesh.start()

    log.info("Gateway em operação — Ctrl+C para encerrar")
    ops = db.list_operators()
    log.info(f"Operadores ativos: {len(ops)}")
    for op in ops:
        log.info(f"  {op['callsign']} → node {op['node_id']}")

    # Loop principal
    while True:
        time.sleep(30)
        status = "online" if aprs_is.connected else "OFFLINE"
        log.info(f"Heartbeat — APRS-IS: {status}")

if __name__ == "__main__":
    main()
