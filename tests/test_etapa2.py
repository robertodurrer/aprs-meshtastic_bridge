#!/usr/bin/env python3
"""
Teste de validação — Etapa 2
Testa a interface Meshtastic sem exigir nó conectado (testes unitários)
+ testes de integração quando o nó está presente.

Uso: python tests/test_etapa2.py [--com-no]
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser()
parser.add_argument("--com-no", action="store_true",
                    help="Inclui testes que exigem nó USB conectado")
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

print("\n── Etapa 2: Verificação da interface Meshtastic ──────")

# Imports
try:
    import meshtastic
    import meshtastic.serial_interface
    from pubsub import pub
    check("import meshtastic", True)
    check("import pubsub", True)
except ImportError as e:
    check("import meshtastic / pubsub", False, str(e))

# Módulo carrega
try:
    from modules.meshtastic_interface import MeshtasticInterface
    from modules.config_loader import load
    cfg = load()
    iface_obj = MeshtasticInterface(cfg)
    check("MeshtasticInterface instancia sem erro", True)
    check("Canal APRS configurado corretamente",
          iface_obj.aprs_channel == cfg["meshtastic"]["aprs_channel_index"])
    check("Intervalo de reconexão configurado",
          iface_obj.reconnect_interval > 0)
except Exception as e:
    check("MeshtasticInterface instancia sem erro", False, str(e))

# Callback registration
try:
    called = []
    iface_obj.on_position(lambda p: called.append(("pos", p)))
    iface_obj.on_message(lambda m: called.append(("msg", m)))
    check("Callbacks registrados sem erro", True)
except Exception as e:
    check("Callbacks registrados sem erro", False, str(e))

# Packet parsing logic (sem nó real)
try:
    from modules.meshtastic_interface import MeshtasticInterface
    mi = MeshtasticInterface(cfg)
    received = []
    mi.on_position(lambda p: received.append(p))

    fake_pos_packet = {
        "fromId": "!aabbccdd",
        "toId": "^all",
        "channel": 1,
        "decoded": {
            "portnum": "POSITION_APP",
            "position": {
                "latitudeI":  -230500000,
                "longitudeI": -451200000,
                "altitude": 750,
            }
        }
    }
    mi._receive(fake_pos_packet, None)
    check("Pacote de posição parseado corretamente", len(received) == 1)
    if received:
        p = received[0]
        check("Latitude extraída corretamente",
              abs(p["latitude"] - (-23.05)) < 0.001,
              f"got {p['latitude']}")
        check("Longitude extraída corretamente",
              abs(p["longitude"] - (-45.12)) < 0.001,
              f"got {p['longitude']}")
        check("Altitude extraída corretamente", p["altitude"] == 750)

    # Teste de filtragem por canal
    received_msg = []
    mi.on_message(lambda m: received_msg.append(m))

    fake_msg_aprs = {
        "fromId": "!aabbccdd", "toId": "^all", "channel": 1,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "PY5XX: olá"}
    }
    fake_msg_longfast = {
        "fromId": "!aabbccdd", "toId": "^all", "channel": 0,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "mensagem longfast"}
    }
    mi._receive(fake_msg_aprs, None)
    mi._receive(fake_msg_longfast, None)
    check("Mensagem no canal APRS aceita", len(received_msg) == 1)
    check("Mensagem no LongFast (ch=0) ignorada", len(received_msg) == 1)

except Exception as e:
    check("Parsing de pacotes (mock)", False, str(e))

# Testes com nó real (opcional)
if args.com_no:
    print("\n── Com nó USB conectado ──────────────────────────────")
    try:
        import meshtastic.serial_interface as msi
        iface_real = msi.SerialInterface()
        check("Nó Meshtastic detectado via USB", True)

        info = iface_real.getMyNodeInfo()
        node_id = info.get("user", {}).get("id", "")
        check("getMyNodeInfo() retorna ID válido", bool(node_id), node_id)

        nodes = iface_real.nodes or {}
        check("nodes[] acessível", isinstance(nodes, dict))
        check(f"Nós conhecidos na mesh: {len(nodes)}", len(nodes) >= 1)

        iface_real.close()
        check("Conexão encerrada limpa", True)
    except Exception as e:
        check("Conexão com nó real", False, str(e))
else:
    skip("Testes com nó USB", "use --com-no quando o nó estiver conectado")

# tools existem
for t in ["tools/detect_serial.py", "tools/listen_packets.py"]:
    check(f"Arquivo {t}", (Path(__file__).parent.parent / t).exists())

# Resumo
print("\n── Resultado ─────────────────────────────────────────")
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"\033[32m  ETAPA 2 CONCLUÍDA — {passed}/{total} verificações OK\033[0m")
    if not args.com_no:
        print("  ► Próximo: conecte o nó e rode: python tests/test_etapa2.py --com-no")
    else:
        print("  Pronto para avançar à Etapa 3.\n")
    sys.exit(0)
else:
    print(f"\033[31m  ATENÇÃO — {passed}/{total} OK, {total-passed} falha(s)\033[0m")
    sys.exit(1)
