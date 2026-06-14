"""
Etapa 3 — Validação de indicativo e passcode APRS-IS.
"""
import socket
from modules.logger import get_logger

log = get_logger("aprs_auth")

APRS_IS_HOST = "rotate.aprs2.net"
APRS_IS_PORT = 14580

def calc_passcode(callsign: str) -> int:
    """Calcula o passcode padrão APRS-IS a partir do indicativo."""
    call = callsign.upper().split("-")[0]
    hash_val = 0x73e2
    i = 0
    while i < len(call):
        hash_val ^= ord(call[i]) << 8
        if i + 1 < len(call):
            hash_val ^= ord(call[i + 1])
        i += 2
    return hash_val & 0x7FFF

def validate_passcode(callsign: str, passcode: int) -> bool:
    """Valida localmente se o passcode bate com o indicativo."""
    expected = calc_passcode(callsign)
    ok = (expected == passcode)
    if not ok:
        log.warning(f"Passcode inválido para {callsign}: "
                    f"informado={passcode}, esperado={expected}")
    return ok

def validate_with_aprs_is(callsign: str, passcode: int,
                           timeout: int = 10) -> tuple[bool, str]:
    """
    Testa o par callsign/passcode conectando ao APRS-IS.
    Retorna (sucesso, mensagem).
    """
    # Primeiro valida localmente
    if not validate_passcode(callsign, passcode):
        return False, f"Passcode {passcode} não corresponde ao indicativo {callsign}"

    # Depois testa contra o servidor
    try:
        sock = socket.create_connection((APRS_IS_HOST, APRS_IS_PORT),
                                        timeout=timeout)
        banner = sock.recv(512).decode("ascii", errors="ignore")
        log.debug(f"APRS-IS banner: {banner.strip()}")

        login = f"user {callsign} pass {passcode} vers MeshAPRS-GW 0.1\r\n"
        sock.send(login.encode())

        response = sock.recv(512).decode("ascii", errors="ignore")
        log.debug(f"APRS-IS response: {response.strip()}")
        sock.close()

        # Resposta de sucesso contém "verified" ou não contém "unverified"
        if "unverified" in response.lower():
            return False, f"APRS-IS rejeitou o par {callsign}/{passcode}"

        log.info(f"APRS-IS validou: {callsign}")
        return True, f"Indicativo {callsign} validado com sucesso"

    except socket.timeout:
        # Sem internet — aceita se passcode local está correto
        log.warning("Timeout ao conectar APRS-IS — usando validação local")
        return True, f"Validado localmente (sem conexão APRS-IS): {callsign}"
    except Exception as e:
        log.error(f"Erro na validação APRS-IS: {e}")
        return False, f"Erro ao conectar APRS-IS: {e}"

def suggest_ssid(callsign: str, existing_ssids: list) -> str:
    """Sugere o SSID completo para o operador."""
    base = callsign.upper().split("-")[0]
    # SSIDs comuns para gateway/mesh: -10 a -15
    for ssid_n in range(10, 16):
        candidate = f"{base}-{ssid_n}"
        if candidate not in existing_ssids:
            return candidate
    return f"{base}-10"
