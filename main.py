#!/usr/bin/env python3
"""
Mesh↔APRS Gateway — main.py
Etapa 5: mensagens Meshtastic → APRS (com ACK e retry)
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
from modules.message_router import MessageRouter
from modules.aprs_format import parse_aprs_message

log = get_logger("gateway")
cfg = load_config()

db      = Database(cfg)
aprs_is = APRSISConnection(cfg)
mesh    = MeshtasticInterface(cfg)
pos_hdl = PositionHandler(db, aprs_is)
router  = MessageRouter(db, aprs_is, mesh_iface=mesh)

def on_position(payload):
    pos_hdl.handle(payload)

def on_mesh_message(payload):
    router.handle_mesh_message(payload)

def on_aprs_is_packet(raw_line: str):
    parsed = parse_aprs_message(raw_line)
    if not parsed:
        return
    if parsed["type"] == "ack":
        router.handle_ack(parsed)
    elif parsed["type"] == "message":
        log.info(f"MSG APRS→Mesh recebida (etapa 6): "
                 f"{parsed['src']} → {parsed['dst']}: {parsed['body'][:50]}")

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

    aprs_is.on_packet(on_aprs_is_packet)
    aprs_is.start()
    time.sleep(2)

    mesh.on_position(on_position)
    mesh.on_message(on_mesh_message)
    mesh.start()

    log.info("Gateway em operação — Ctrl+C para encerrar")
    ops = db.list_operators()
    log.info(f"Operadores ativos: {len(ops)}")
    for op in ops:
        log.info(f"  {op['callsign']} → node {op['node_id']}")

    while True:
        time.sleep(30)
        status = "online" if aprs_is.connected else "OFFLINE"
        log.info(f"Heartbeat — APRS-IS: {status}")

if __name__ == "__main__":
    main()
