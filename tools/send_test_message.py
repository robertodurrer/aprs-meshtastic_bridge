#!/usr/bin/env python3
"""
Envia uma mensagem de teste pelo nó Meshtastic, no canal APRS,
simulando o que um operador digitaria no app.

Uso:
  python tools/send_test_message.py "PU2OZH-4 teste de mensagem via mesh"
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

if len(sys.argv) < 2:
    print("Uso: python tools/send_test_message.py \"CALLSIGN corpo da mensagem\"")
    sys.exit(1)

text = sys.argv[1]

from modules.config_loader import load as load_config
from modules.meshtastic_interface import MeshtasticInterface

cfg = load_config()
mesh = MeshtasticInterface(cfg)

print(f"\n  Conectando ao nó Meshtastic...")
if not mesh.connect():
    print("  ✗ Falha ao conectar")
    sys.exit(1)

ch = cfg["meshtastic"]["aprs_channel_index"]
print(f"  Enviando no canal {ch} (APRS): '{text}'")
ok = mesh.send_text(text, destination_id="^all", channel_index=ch)

if ok:
    print(f"  ✓ Mensagem enviada. Acompanhe o log do gateway (main.py)")
    print(f"    ou rode: tail -f logs/gateway.log")
else:
    print(f"  ✗ Falha ao enviar")

time.sleep(2)
mesh.stop()
