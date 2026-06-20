"""Carrega e valida a configuração do gateway."""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"

class ConfigError(Exception):
    """Erro de configuração."""
    pass

def _validate_config(cfg: Dict[str, Any]) -> None:
    """Valida a estrutura básica da configuração."""
    required_sections = ["gateway", "database", "meshtastic"]
    for section in required_sections:
        if section not in cfg:
            raise ConfigError(f"Seção obrigatória '{section}' não encontrada")
    
    # Validações específicas
    gw = cfg["gateway"]
    required_gw_fields = ["callsign", "passcode", "aprs_is_host", "aprs_is_port"]
    for field in required_gw_fields:
        if field not in gw:
            raise ConfigError(f"Campo obrigatório 'gateway.{field}' não encontrado")
    
    # Valida callsign
    callsign = gw["callsign"].upper()
    if not (3 <= len(callsign.split('-')[0]) <= 6):
        raise ConfigError(f"Callsign inválido: {callsign}")
    
    # Valida passcode (pode ser -1 para teste)
    if not isinstance(gw["passcode"], int):
        raise ConfigError("Passcode deve ser um número inteiro")

def load() -> dict:
    """Carrega e valida a configuração do gateway."""
    try:
        if not CONFIG_PATH.exists():
            raise ConfigError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}")
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        _validate_config(cfg)
        
        # Override com variáveis de ambiente se existirem
        if os.getenv("GW_CALLSIGN"):
            cfg["gateway"]["callsign"] = os.getenv("GW_CALLSIGN")
        if os.getenv("GW_PASSCODE"):
            try:
                cfg["gateway"]["passcode"] = int(os.getenv("GW_PASSCODE"))
            except ValueError:
                raise ConfigError("GW_PASSCODE deve ser um número inteiro")
        
        return cfg
        
    except json.JSONDecodeError as e:
        raise ConfigError(f"Erro ao decodificar JSON: {e}")
    except FileNotFoundError:
        raise ConfigError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}")
    except Exception as e:
        raise ConfigError(f"Erro ao carregar configuração: {e}")

if __name__ == "__main__":
    cfg = load()
    print(json.dumps(cfg, indent=2))
