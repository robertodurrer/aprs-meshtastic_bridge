#!/usr/bin/env python3
"""
Teste de validação — Etapa 5
Uso: python tests/test_etapa5.py [--online] [--end-to-end CALLSIGN_DESTINO]
"""
import sys
import time
import argparse
import threading as th
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser()
parser.add_argument("--online", action="store_true",
                    help="Envia mensagem real ao APRS-IS")
parser.add_argument("--end-to-end", metavar="CALLSIGN",
                    help="Testa fluxo completo Mesh→APRS-IS para um callsign real "
                         "(ex: PU2OZH-4). Requer nó Meshtastic conectado.")
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

print("\n── Etapa 5: Mensagens Meshtastic → APRS ──────────────")

from modules.config_loader import load
from modules.database import Database
from modules.message_router import MessageRouter
import sqlite3, threading as th2

cfg = load()

class TestDB(Database):
    def __init__(self):
        self.path = ":memory:"
        self._local = th2.local()
        self._init_schema()

class MockAPRS:
    def __init__(self, online=True):
        self.sent = []
        self.connected = online
    def send(self, pkt):
        self.sent.append(pkt)
        return True

class MockMesh:
    def __init__(self):
        self.sent_texts = []
    def send_text(self, text, destination_id="^all", channel_index=None):
        self.sent_texts.append(text)
        return True

# ── parse_destination ──────────────────────────────────────────
db = TestDB()
aprs_mock = MockAPRS()
router = MessageRouter(db, aprs_mock)

p1 = router.parse_destination("PY5XX: olá mundo")
check("parse_destination com ':'", p1 == ("PY5XX", "olá mundo"))

p2 = router.parse_destination("PU2OZH-4 teste sem dois pontos")
check("parse_destination sem ':'", p2 == ("PU2OZH-4", "teste sem dois pontos"))

p3 = router.parse_destination("mensagem qualquer sem callsign valido")
check("parse_destination sem callsign retorna None", p3 is None)

p4 = router.parse_destination("")
check("parse_destination string vazia retorna None", p4 is None)

p5 = router.parse_destination("PY5XX:")
check("parse_destination sem corpo retorna None", p5 is None)

# ── handle_mesh_message — fluxo completo com mock ─────────────
db.add_operator("PU2OZH-10", "PU2OZH-10", 19376,
                node_id="!f714909c", tx_aprs=True)

router.handle_mesh_message({
    "from_id": "!f714909c",
    "text": "PU2OZH-4 mensagem de teste",
    "channel": 1,
})
check("Mensagem válida enviada ao APRS mock", len(aprs_mock.sent) == 1)
check("Pacote contém origem e destino",
      aprs_mock.sent and "PU2OZH-10" in aprs_mock.sent[0]
      and "PU2OZH-4" in aprs_mock.sent[0])

msgs = db.list_messages()
check("Mensagem registrada no banco", len(msgs) == 1)
check("Status inicial é 'pending'", msgs[0]["status"] == "pending")

# Nó não cadastrado
router.handle_mesh_message({
    "from_id": "!00000000",
    "text": "PY5XX teste de nó desconhecido",
    "channel": 1,
})
check("Nó não cadastrado não gera envio", len(aprs_mock.sent) == 1)

# tx_aprs=0
db.update_operator("PU2OZH-10", tx_aprs=False)
router.handle_mesh_message({
    "from_id": "!f714909c",
    "text": "PU2OZH-4 esta não deve sair",
    "channel": 1,
})
check("tx_aprs=0 bloqueia envio", len(aprs_mock.sent) == 1)
db.update_operator("PU2OZH-10", tx_aprs=True)

# Mensagem sem callsign reconhecível
router.handle_mesh_message({
    "from_id": "!f714909c",
    "text": "isso aqui não tem destino válido nenhum",
    "channel": 1,
})
check("Mensagem sem callsign válido descartada", len(aprs_mock.sent) == 1)

# ── ACK handling ────────────────────────────────────────────
db2 = TestDB()
aprs_mock2 = MockAPRS()
mesh_mock = MockMesh()
router2 = MessageRouter(db2, aprs_mock2, mesh_iface=mesh_mock)

db2.add_operator("PU2OZH-10", "PU2OZH-10", 19376, node_id="!f714909c")
router2.handle_mesh_message({
    "from_id": "!f714909c",
    "text": "PU2OZH-4 aguardando ack",
    "channel": 1,
})
check("Mensagem registrada como pending no router",
      "001" in router2._pending)

router2.handle_ack({"msg_id": "001", "src": "PU2OZH-4", "dst": "PU2OZH-10"})
check("ACK remove da fila pending", "001" not in router2._pending)

msgs2 = db2.list_messages()
check("Status atualizado para 'delivered'", msgs2[0]["status"] == "delivered")
check("Mesh notificado sobre entrega", len(mesh_mock.sent_texts) == 1)

# ACK para msg_id desconhecido não quebra
try:
    router2.handle_ack({"msg_id": "999", "src": "X", "dst": "Y"})
    check("ACK desconhecido não gera exceção", True)
except Exception as e:
    check("ACK desconhecido não gera exceção", False, str(e))

# ── Retry / timeout (versão acelerada para teste) ─────────────
import modules.message_router as mr_module
original_timeout = mr_module.ACK_TIMEOUT_S
mr_module.ACK_TIMEOUT_S = 2  # acelera o teste

db3 = TestDB()
aprs_mock3 = MockAPRS()
router3 = MessageRouter(db3, aprs_mock3)
db3.add_operator("PU2OZH-10", "PU2OZH-10", 19376, node_id="!f714909c")

router3.handle_mesh_message({
    "from_id": "!f714909c",
    "text": "PU2OZH-9 teste retry",
    "channel": 1,
})
time.sleep(3.5)  # aguarda 1 retry (timeout=2s)
check("Retry reenviou o pacote", len(aprs_mock3.sent) >= 2)

mr_module.ACK_TIMEOUT_S = original_timeout

# Arquivos
for f in ["modules/message_router.py", "tools/send_test_message.py"]:
    check(f"Arquivo {f}", (Path(__file__).parent.parent / f).exists())

# ── Online: envio real ─────────────────────────────────────────
if args.online:
    print("\n── Envio real ao APRS-IS ─────────────────────────────")
    from modules.aprs_is_connection import APRSISConnection
    aprs_real = APRSISConnection(cfg)
    db_real = Database(cfg)
    router_real = MessageRouter(db_real, aprs_real)

    received_acks = []
    def on_pkt(line):
        from modules.aprs_format import parse_aprs_message
        p = parse_aprs_message(line)
        if p and p["type"] == "ack":
            received_acks.append(p)
            router_real.handle_ack(p)

    aprs_real.on_packet(on_pkt)
    connected = aprs_real.start()
    time.sleep(3)
    check("Conectou ao APRS-IS", aprs_real.connected)

    dst = args.end_to_end or "PU2OZH-4"
    print(f"  Enviando mensagem de teste para {dst}...")
    router_real.handle_mesh_message({
        "from_id": "!f714909c",
        "text": f"{dst} teste etapa5 {int(time.time())%1000}",
        "channel": 1,
    })
    check("Mensagem enviada (verificar no destino)", True)
    print(f"  Aguardando ACK por até 30s...")
    time.sleep(30)
    check(f"ACK recebido de {dst}", len(received_acks) > 0,
          "se falhar, confirme que o tracker está online e recebendo")
    aprs_real.stop()
else:
    skip("Envio real ao APRS-IS", "use --online")

# ── End-to-end completo (nó Meshtastic real) ───────────────────
if args.end_to_end:
    print(f"\n── End-to-end via nó Meshtastic real → {args.end_to_end} ──")
    from modules.meshtastic_interface import MeshtasticInterface
    from modules.aprs_is_connection import APRSISConnection
    from modules.aprs_format import parse_aprs_message

    db_e2e = Database(cfg)
    aprs_e2e = APRSISConnection(cfg)
    router_e2e = MessageRouter(db_e2e, aprs_e2e)
    acks_e2e = []

    def on_pkt_e2e(line):
        p = parse_aprs_message(line)
        if p and p["type"] == "ack":
            acks_e2e.append(p)
            router_e2e.handle_ack(p)
        elif p and p["type"] == "message":
            log_line = f"  ← Recebido de {p['src']}: {p['body']}"
            print(log_line)

    aprs_e2e.on_packet(on_pkt_e2e)
    aprs_e2e.start()
    time.sleep(3)
    check("APRS-IS conectado (e2e)", aprs_e2e.connected)

    mesh_e2e = MeshtasticInterface(cfg)
    mesh_e2e.on_message(lambda p: router_e2e.handle_mesh_message(p))
    connected_mesh = mesh_e2e.connect()
    check("Nó Meshtastic conectado (e2e)", connected_mesh)

    if connected_mesh:
        print(f"\n  ► Envie pelo app Meshtastic, no canal APRS, a mensagem:")
        print(f"    \033[33m{args.end_to_end} teste manual end-to-end\033[0m")
        print(f"  Aguardando até 60s pela mensagem e o ACK...")
        deadline = time.time() + 60
        while time.time() < deadline and not acks_e2e:
            time.sleep(2)
        check("ACK completo recebido (mesh → aprs-is → tracker → ack)",
              len(acks_e2e) > 0)

    mesh_e2e.stop()
    aprs_e2e.stop()

# ── Resultado ─────────────────────────────────────────────────
print("\n── Resultado ─────────────────────────────────────────")
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"\033[32m  ETAPA 5 CONCLUÍDA — {passed}/{total} verificações OK\033[0m")
    if not args.online:
        print("  ► Rode: python tests/test_etapa5.py --online")
    if not args.end_to_end:
        print("  ► Rode: python tests/test_etapa5.py --online --end-to-end PU2OZH-4")
    print()
    sys.exit(0)
else:
    print(f"\033[31m  ATENÇÃO — {passed}/{total} OK, {total-passed} falha(s)\033[0m\n")
    sys.exit(1)
