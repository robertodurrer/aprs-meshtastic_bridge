#!/usr/bin/env python3
"""
Mesh↔APRS Gateway — main.py
Etapa 5: mensagens Meshtastic → APRS (com ACK e retry)
"""
import sys
import time
import signal
import traceback
import atexit
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config_loader import load as load_config, ConfigError
from modules.logger import get_logger
from modules.database import Database
from modules.meshtastic_interface import MeshtasticInterface
from modules.aprs_is_connection import APRSISConnection
from modules.position_handler import PositionHandler
from modules.message_router import MessageRouter
from modules.aprs_format import parse_aprs_message
import subprocess
import threading

try:
    cfg = load_config()
    log = get_logger("gateway", cfg)
except ConfigError as e:
    print(f"ERRO DE CONFIGURAÇÃO: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERRO FATAL ao carregar configuração: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

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

def shutdown(sig=None, frame=None):
    log.info("Encerrando gateway...")
    try:
        mesh.stop()
        aprs_is.stop()
        log.info("Gateway encerrado com sucesso")
    except Exception as e:
        log.error(f"Erro durante encerramento: {e}")
    if sig is not None:
        sys.exit(0)

def run_webui():
    """Start the web UI in a separate process."""
    try:
        from webui.app import app
        import uvicorn
        
        host = cfg.get("webui", {}).get("host", "0.0.0.0") 
        port = cfg.get("webui", {}).get("port", 8080)
        log.info(f"Web UI iniciando em http://{host}:{port}")
        
        # Run in current process using uvicorn
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        log.error(f"Falha ao iniciar Web UI: {e}")

def main():
    # Start web UI if enabled in config
    if cfg.get("webui", {}).get("enabled", False):
        webui_thread = threading.Thread(target=run_webui, daemon=True)
        webui_thread.start()
        log.info(f"Web UI iniciando em http://{cfg['webui']['host']}:{cfg['webui']['port']}")
    
    log.info("═══════════════════════════════════════")
    log.info("  Mesh↔APRS Gateway  —  iniciando")
    log.info(f"  Callsign: {cfg['gateway']['callsign']}")
    log.info("═══════════════════════════════════════")

    # Registra cleanup automático
    atexit.register(shutdown)
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        # Verifica se o banco está acessível
        db.list_operators()
        log.info("Banco de dados OK")

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

        # Loop principal com tratamento de exceções
        heartbeat_counter = 0
        while True:
            try:
                time.sleep(30)
                heartbeat_counter += 1
                status = "online" if aprs_is.connected else "OFFLINE"
                log.info(f"Heartbeat #{heartbeat_counter} — APRS-IS: {status}")
                
                # Verifica saúde do sistema a cada 5 minutos
                if heartbeat_counter % 10 == 0:
                    mesh_status = "connected" if mesh.iface else "disconnected"
                    log.info(f"Status: APRS-IS={status}, Meshtastic={mesh_status}")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Erro no heartbeat: {e}")
                
    except Exception as e:
        log.error(f"Erro fatal no loop principal: {e}")
        traceback.print_exc()
        shutdown(None, None)

if __name__ == "__main__":
    main()
