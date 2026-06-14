#!/usr/bin/env python3
"""
Teste de validação — Etapa 1
Executa: python tests/test_etapa1.py
Todos os itens devem mostrar OK para avançar à etapa 2.
"""
import sys
import json
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PASS = "\033[32m  [OK]\033[0m"
FAIL = "\033[31m  [FAIL]\033[0m"
results = []

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"{status} {label}" + (f" — {detail}" if detail else ""))
    results.append(condition)

print("\n── Etapa 1: Verificação do ambiente ──────────────────")

# Python
import sys
v = sys.version_info
check(f"Python {v.major}.{v.minor}.{v.micro}", v >= (3, 11),
      "recomendado 3.11+" if v < (3, 11) else "")

# Libs obrigatórias
for lib in ["meshtastic", "aprslib", "fastapi", "uvicorn",
            "pydantic", "serial", "bleak", "requests", "dotenv"]:
    try:
        importlib.import_module(lib)
        check(f"import {lib}", True)
    except ImportError as e:
        check(f"import {lib}", False, str(e))

# Estrutura de diretórios
base = Path(__file__).parent.parent
for d in ["db", "modules", "tests", "logs", "config"]:
    check(f"Diretório {d}/", (base / d).is_dir())

# Arquivos essenciais
for f in ["main.py", "config/config.json", "config/.env",
          ".gitignore", "modules/config_loader.py", "modules/logger.py"]:
    check(f"Arquivo {f}", (base / f).exists())

# Config carrega e tem campos obrigatórios
try:
    from modules.config_loader import load
    cfg = load()
    check("config.json carrega sem erro", True)
    check("config.gateway.callsign existe", "callsign" in cfg["gateway"])
    check("config.meshtastic.aprs_channel_index existe",
          "aprs_channel_index" in cfg["meshtastic"])
except Exception as e:
    check("config.json carrega sem erro", False, str(e))

# Logger
try:
    from modules.logger import get_logger
    log = get_logger("test")
    log.info("logger teste OK")
    check("Logger inicializa sem erro", True)
except Exception as e:
    check("Logger inicializa sem erro", False, str(e))

# .env permissions
env_path = base / "config" / ".env"
if env_path.exists():
    import stat
    mode = oct(stat.S_IMODE(env_path.stat().st_mode))
    check(f".env permissões restritas ({mode})", mode == "0o600")

# Resumo
print("\n── Resultado ─────────────────────────────────────────")
passed = sum(results)
total = len(results)
if passed == total:
    print(f"\033[32m  ETAPA 1 CONCLUÍDA — {passed}/{total} verificações OK\033[0m")
    print("  Pronto para avançar à Etapa 2.\n")
    sys.exit(0)
else:
    print(f"\033[31m  ATENÇÃO — {passed}/{total} OK, {total-passed} falha(s)\033[0m")
    print("  Corrija os itens marcados [FAIL] antes de avançar.\n")
    sys.exit(1)
