#!/usr/bin/env python3
"""
Escuta ao vivo todos os pacotes recebidos pelo nó Meshtastic.
Útil para validar recepção e filtro de canal durante a Etapa 2.

Uso: python tools/listen_packets.py [--channel N] [--duration S]
Ctrl+C para encerrar.
"""
import sys
import json
import time
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.config_loader import load as load_config
from modules.logger import get_logger

parser = argparse.ArgumentParser()
parser.add_argument("--channel", type=int, default=None,
                    help="Filtrar por canal (padrão: todos)")
parser.add_argument("--duration", type=int, default=0,
                    help="Duração em segundos (0 = indefinido)")
args = parser.parse_args()

cfg = load_config()
log = get_logger("listen")
aprs_ch = cfg["meshtastic"]["aprs_channel_index"]

print(f"\n── Escuta de pacotes Meshtastic ──────────────────────")
print(f"  Canal APRS configurado : {aprs_ch}")
print(f"  Filtro ativo           : {'ch=' + str(args.channel) if args.channel is not None else 'todos os canais'}")
print(f"  Duração                : {'indefinida' if not args.duration else str(args.duration)+'s'}")
print(f"  Ctrl+C para encerrar\n")

counts = {"total": 0, "position": 0, "message": 0, "other": 0}

def on_receive(packet, interface):
    channel = packet.get("channel", 0)
    if args.channel is not None and channel != args.channel:
        return

    decoded  = packet.get("decoded", {})
    portnum  = decoded.get("portnum", "UNKNOWN")
    from_id  = packet.get("fromId", "?")
    to_id    = packet.get("toId", "^all")
    counts["total"] += 1

    marker = " ◄ CANAL APRS" if channel == aprs_ch else ""

    if portnum == "POSITION_APP":
        counts["position"] += 1
        pos = decoded.get("position", {})
        lat = pos.get("latitudeI", 0) / 1e7
        lon = pos.get("longitudeI", 0) / 1e7
        alt = pos.get("altitude", 0)
        print(f"  [{counts['total']:04d}] POSIÇÃO  ch={channel}{marker}")
        print(f"         de={from_id} → {lat:.5f},{lon:.5f} alt={alt}m")

    elif portnum == "TEXT_MESSAGE_APP":
        counts["message"] += 1
        text = decoded.get("text", "")
        print(f"  [{counts['total']:04d}] MENSAGEM ch={channel}{marker}")
        print(f"         de={from_id} para={to_id}: '{text[:80]}'")

    elif portnum == "NODEINFO_APP":
        counts["other"] += 1
        user = decoded.get("user", {})
        print(f"  [{counts['total']:04d}] NODEINFO ch={channel}")
        print(f"         de={from_id}: {user.get('longName','?')} ({user.get('shortName','?')})")

    else:
        counts["other"] += 1
        print(f"  [{counts['total']:04d}] {portnum:<20} ch={channel}{marker} de={from_id}")

import meshtastic.serial_interface
from pubsub import pub

try:
    iface = meshtastic.serial_interface.SerialInterface()
    pub.subscribe(on_receive, "meshtastic.receive")
    print(f"  Conectado. Aguardando pacotes...\n")

    start = time.time()
    while True:
        time.sleep(1)
        if args.duration and (time.time() - start) >= args.duration:
            break

except KeyboardInterrupt:
    pass
except Exception as e:
    print(f"\n  ERRO: {e}")
finally:
    print(f"\n── Resumo ────────────────────────────────────────────")
    print(f"  Total      : {counts['total']}")
    print(f"  Posições   : {counts['position']}")
    print(f"  Mensagens  : {counts['message']}")
    print(f"  Outros     : {counts['other']}")
    print()
    try:
        iface.close()
    except Exception:
        pass
