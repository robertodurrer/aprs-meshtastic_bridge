#!/usr/bin/env python3
"""
Teste de validação — Etapa 4
Uso: python tests/test_etapa4.py [--online] [--com-no]
"""
import sys
import argparse
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser()
parser.add_argument("--online", action="store_true",
                    help="Testa envio real ao APRS-IS")
parser.add_argument("--com-no", action="store_true",
                    help="Testa com nó Meshtastic conectado")
args = parser.parse_args()

PASS = "\033[32m  [OK]\033[0m"
FAIL = "\033[31m  [FAIL]\033[0m"
SKIP = "\033[33m  [SKIP]\033[0m"
results = []

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"{status} {label}" + (f" — {detail}" if detail else ""))
    results.append(condition)

def skip(label, reason=""):
    print(f"{SKIP} {label}" + (f" — {reason}" if reason else ""))

print("\n── Etapa 4: Posição Meshtastic → APRS-IS ────────────")

from modules.aprs_format import (format_position, format_message,
                                  format_ack, parse_aprs_message)
from modules.config_loader import load
cfg = load()

# ── Formatação de posição ─────────────────────────────────────
# São José dos Campos: -23.1896, -45.8841
pkt = format_position("PU2OZH-10", -23.1896, -45.8841,
                       icon="/>", comment="via Mesh/APRS-GW",
                       altitude_m=604)
check("format_position retorna string", isinstance(pkt, str))
check("callsign no pacote",     "PU2OZH-10" in pkt)
check("header APRS correto",    ">APMT,TCPIP*:=" in pkt)
check("hemisférios corretos",   "S" in pkt and "W" in pkt)
check("ícone presente",         "/>" in pkt)
check("comentário presente",    "via Mesh/APRS-GW" in pkt)
check("altitude presente",      "/A=" in pkt)
print(f"       Pacote: {pkt}")

# Posição no hemisfério norte/leste (teste de sinal)
pkt_ne = format_position("PP1TEST", 48.8566, 2.3522)
check("Hemisfério N/E correto", "N" in pkt_ne and "E" in pkt_ne)

# ── Formatação de mensagem ────────────────────────────────────
msg = format_message("PU2OZH-10", "PY5XX", "olá mundo", "001")
check("format_message correto",  ":PY5XX    :olá mundo{001}" in msg)

ack = format_ack("PU2OZH-10", "PY5XX", "001")
check("format_ack correto",      ":PY5XX    :ack001" in ack)

# ── Parse de mensagem APRS-IS ─────────────────────────────────
raw_msg = "PY5XX>APRS,TCPIP*::PU2OZH-10:teste de mensagem{042}"
parsed = parse_aprs_message(raw_msg)
check("parse_aprs_message tipo",   parsed and parsed["type"] == "message")
check("parse src correto",         parsed and parsed["src"] == "PY5XX")
check("parse dst correto",         parsed and parsed["dst"] == "PU2OZH-10")
check("parse body correto",        parsed and parsed["body"] == "teste de mensagem")
check("parse msg_id correto",      parsed and parsed["msg_id"] == "042")

raw_ack = "PY5XX>APRS,TCPIP*::PU2OZH-10:ack001"
parsed_ack = parse_aprs_message(raw_ack)
check("parse ACK detectado",       parsed_ack and parsed_ack["type"] == "ack")

# ── PositionHandler com mock ──────────────────────────────────
from modules.database import Database
from modules.position_handler import PositionHandler
import sqlite3, threading as th

class MockAPRS:
    def __init__(self): self.sent = []; self.connected = True
    def send(self, pkt): self.sent.append(pkt); return True

class TestDB(Database):
    def __init__(self):
        self.path = ":memory:"
        self._local = th.local()
        self._init_schema()

db_test = TestDB()
db_test.add_operator("PU2OZH-10", "PU2OZH-10", 19376,
                     node_id="!f714909c", pub_position=True)
mock_aprs = MockAPRS()
hdl = PositionHandler(db_test, mock_aprs)

hdl.handle({
    "from_id": "!f714909c",
    "latitude": -23.1896, "longitude": -45.8841,
    "altitude": 604, "speed": 0, "course": 0,
})
check("PositionHandler envia para APRS mock", len(mock_aprs.sent) == 1)
check("Pacote contém callsign correto",
      mock_aprs.sent and "PU2OZH-10" in mock_aprs.sent[0])

# Nó não cadastrado — deve ignorar
hdl.handle({
    "from_id": "!00000000",
    "latitude": -23.0, "longitude": -45.0,
    "altitude": 0, "speed": 0, "course": 0,
})
check("Nó não cadastrado ignorado", len(mock_aprs.sent) == 1)

# pub_position=0 — deve ignorar
db_test.update_operator("PU2OZH-10", pub_position=0)
hdl.handle({
    "from_id": "!f714909c",
    "latitude": -23.0, "longitude": -45.0,
    "altitude": 0, "speed": 0, "course": 0,
})
check("pub_position=0 ignorado", len(mock_aprs.sent) == 1)
db_test.update_operator("PU2OZH-10", pub_position=1)

# Arquivos
for f in ["modules/aprs_format.py", "modules/aprs_is_connection.py",
          "modules/position_handler.py"]:
    check(f"Arquivo {f}", (Path(__file__).parent.parent / f).exists())

# ── Online ────────────────────────────────────────────────────
if args.online:
    print("\n── Envio real ao APRS-IS ─────────────────────────────")
    from modules.aprs_is_connection import APRSISConnection
    aprs = APRSISConnection(cfg)
    connected = aprs.connect()
    check("Conectou ao APRS-IS", connected)
    if connected:
        pkt_real = format_position(
            cfg["gateway"]["callsign"],
            -23.1896, -45.8841,
            comment="TESTE Mesh/APRS-GW etapa4",
            altitude_m=604
        )
        sent = aprs.send(pkt_real)
        check("Pacote de posição enviado", sent)
        print(f"       Pacote: {pkt_real}")
        print(f"\n  \033[33m► Verifique em: https://aprs.fi/#!call={cfg['gateway']['callsign']}\033[0m")
        time.sleep(2)
        aprs.stop()
else:
    skip("Envio real ao APRS-IS", "use --online para enviar posição real")

# ── Com nó ────────────────────────────────────────────────────
if args.com_no:
    print("\n── Com nó Meshtastic conectado ───────────────────────")
    from modules.meshtastic_interface import MeshtasticInterface
    from modules.aprs_is_connection import APRSISConnection
    from modules.database import Database as DBReal

    db_real   = DBReal(cfg)
    aprs_real = APRSISConnection(cfg)
    hdl_real  = PositionHandler(db_real, aprs_real)

    received = []
    aprs_real.start()
    time.sleep(2)
    check("APRS-IS conectado", aprs_real.connected)

    mesh = MeshtasticInterface(cfg)
    mesh.on_position(lambda p: received.append(p) or hdl_real.handle(p))
    mesh.start()

    print("  Aguardando posição do nó (até 120s)...")
    deadline = time.time() + 120
    while time.time() < deadline and not received:
        time.sleep(2)

    check("Posição recebida do nó real", len(received) > 0)
    if received:
        p = received[0]
        check("Latitude válida",  abs(p["latitude"])  > 0)
        check("Longitude válida", abs(p["longitude"]) > 0)
        print(f"       Posição: {p['latitude']:.5f},{p['longitude']:.5f} alt={p['altitude']}m")

    mesh.stop()
    aprs_real.stop()
else:
    skip("Teste com nó real", "use --com-no para teste end-to-end")

# ── Resultado ─────────────────────────────────────────────────
print("\n── Resultado ─────────────────────────────────────────")
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"\033[32m  ETAPA 4 CONCLUÍDA — {passed}/{total} verificações OK\033[0m")
    if not args.online:
        print("  ► Rode: python tests/test_etapa4.py --online")
    if not args.com_no:
        print("  ► Rode: python tests/test_etapa4.py --online --com-no")
    print()
    sys.exit(0)
else:
    print(f"\033[31m  ATENÇÃO — {passed}/{total} OK, {total-passed} falha(s)\033[0m\n")
    sys.exit(1)
