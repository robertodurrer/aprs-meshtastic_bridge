#!/usr/bin/env python3
"""
Teste de validação — Etapa 3
Uso: python tests/test_etapa3.py [--online]
--online: testa conexão real com APRS-IS
"""
import sys
import argparse
import tempfile
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser()
parser.add_argument("--online", action="store_true",
                    help="Testa validação real contra APRS-IS")
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

print("\n── Etapa 3: Banco de dados e cadastro ────────────────")

# Imports
try:
    from modules.database import Database
    from modules.aprs_auth import (calc_passcode, validate_passcode,
                                    validate_with_aprs_is, suggest_ssid)
    from modules.config_loader import load
    check("Imports OK", True)
except ImportError as e:
    check("Imports OK", False, str(e))
    sys.exit(1)

# ── Passcode ──────────────────────────────────────────────────
check("calc_passcode PU2OZH == 19376",   calc_passcode("PU2OZH")   == 19376)
check("calc_passcode ignora SSID",        calc_passcode("PU2OZH-10") == 19376)
check("validate_passcode correto",        validate_passcode("PU2OZH", 19376))
check("validate_passcode incorreto",      not validate_passcode("PU2OZH", 99999))
check("calc_passcode case-insensitive",   calc_passcode("pu2ozh")   == 19376)

# ── Banco em memória temporária ───────────────────────────────
cfg_test = {"database": {"path": ":memory:"}}

# Patch para usar :memory:
import sqlite3, threading
class TestDB(Database):
    def __init__(self):
        self.path = ":memory:"
        self._local = threading.local()
        self._init_schema()

try:
    db = TestDB()
    check("Database inicializa sem erro", True)
except Exception as e:
    check("Database inicializa sem erro", False, str(e))
    sys.exit(1)

# Add operator
ok1 = db.add_operator("PU2OZH-10", "PU2OZH-10", 19376,
                       node_id="!f714909c", long_name="Roberto",
                       short_name="OZH3")
check("add_operator bem-sucedido", ok1)

# Duplicata rejeitada
ok2 = db.add_operator("PU2OZH-10", "PU2OZH-10", 19376)
check("add_operator duplicata rejeitada", not ok2)

# Busca por callsign
op = db.get_operator_by_callsign("PU2OZH-10")
check("get_operator_by_callsign encontra", op is not None)
check("node_id salvo corretamente", op and op["node_id"] == "!f714909c")
check("long_name salvo corretamente", op and op["long_name"] == "Roberto")
check("active=1 por padrão", op and op["active"] == 1)

# Busca por node_id
op2 = db.get_operator_by_node("!f714909c")
check("get_operator_by_node encontra", op2 is not None)
check("callsign correto via node_id", op2 and op2["callsign"] == "PU2OZH-10")

# Update
db.update_operator("PU2OZH-10", pub_position=0)
op3 = db.get_operator_by_callsign("PU2OZH-10")
check("update_operator pub_position=0", op3 and op3["pub_position"] == 0)

# Disable / list
db.remove_operator("PU2OZH-10")
ops_active = db.list_operators(active_only=True)
check("remove_operator desativa (active=0)", len(ops_active) == 0)
ops_all = db.list_operators(active_only=False)
check("list_operators --todos mostra inativo", len(ops_all) == 1)

# Re-add para testes seguintes
db.add_operator("PU2OZH-10", "PU2OZH-10", 19376,
                node_id="!f714909c", long_name="Roberto")

# Posição
db.save_position("!f714909c", -23.228, -45.924, alt=604,
                 callsign="PU2OZH-10")
pos = db.get_last_position("!f714909c")
check("save_position OK", pos is not None)
check("latitude salva corretamente", pos and abs(pos["latitude"] - (-23.228)) < 0.001)
check("altitude salva corretamente", pos and pos["altitude"] == 604)

# Mensagens
mid = db.save_message("mesh_to_aprs", "PU2OZH-10", "PY5XX", "olá!", "001")
check("save_message retorna ID", mid > 0)
db.update_message_status(mid, "delivered")
msgs = db.list_messages()
check("list_messages retorna mensagem", len(msgs) == 1)
check("status atualizado para delivered", msgs[0]["status"] == "delivered")

# suggest_ssid
existing = ["PU2OZH-10", "PU2OZH-11"]
ssid = suggest_ssid("PU2OZH", existing)
check("suggest_ssid evita existentes", ssid not in existing)
check("suggest_ssid formato correto", ssid.startswith("PU2OZH-"))

# Arquivos
for f in ["modules/database.py", "modules/aprs_auth.py", "manage.py"]:
    check(f"Arquivo {f}", (Path(__file__).parent.parent / f).exists())

# ── Online (opcional) ─────────────────────────────────────────
if args.online:
    print("\n── Validação online APRS-IS ──────────────────────────")
    ok_v, msg_v = validate_with_aprs_is("PU2OZH", 19376)
    check(f"APRS-IS valida PU2OZH/19376", ok_v, msg_v)
    ok_f, msg_f = validate_with_aprs_is("PU2OZH", 99999)
    check(f"APRS-IS rejeita passcode errado", not ok_f, msg_f)
else:
    skip("Validação online APRS-IS", "use --online para testar")

# ── Resultado ─────────────────────────────────────────────────
print("\n── Resultado ─────────────────────────────────────────")
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"\033[32m  ETAPA 3 CONCLUÍDA — {passed}/{total} verificações OK\033[0m")
    if not args.online:
        print("  ► Rode também: python tests/test_etapa3.py --online")
    print("  Pronto para avançar à Etapa 4.\n")
    sys.exit(0)
else:
    print(f"\033[31m  ATENÇÃO — {passed}/{total} OK, {total-passed} falha(s)\033[0m\n")
    sys.exit(1)
