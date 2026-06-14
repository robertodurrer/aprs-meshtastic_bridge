"""Carrega e valida a configuração do gateway."""
import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"

def load() -> dict:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    # Override com variáveis de ambiente se existirem
    if os.getenv("GW_CALLSIGN"):
        cfg["gateway"]["callsign"] = os.getenv("GW_CALLSIGN")
    if os.getenv("GW_PASSCODE"):
        cfg["gateway"]["passcode"] = int(os.getenv("GW_PASSCODE"))
    return cfg

if __name__ == "__main__":
    cfg = load()
    print(json.dumps(cfg, indent=2))
