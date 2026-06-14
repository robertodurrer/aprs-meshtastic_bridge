"""
Etapa 4 — Formatação de pacotes APRS.
Converte dados do Meshtastic para strings APRS válidas.
"""
import time
from datetime import datetime, timezone


def _lat_to_aprs(lat: float) -> str:
    """Converte latitude decimal para formato APRS DDmm.mmN/S."""
    hemi = "N" if lat >= 0 else "S"
    lat  = abs(lat)
    deg  = int(lat)
    mins = (lat - deg) * 60
    return f"{deg:02d}{mins:05.2f}{hemi}"


def _lon_to_aprs(lon: float) -> str:
    """Converte longitude decimal para formato APRS DDDmm.mmE/W."""
    hemi = "E" if lon >= 0 else "W"
    lon  = abs(lon)
    deg  = int(lon)
    mins = (lon - deg) * 60
    return f"{deg:03d}{mins:05.2f}{hemi}"


def format_position(callsign: str, lat: float, lon: float,
                    icon: str = "/>", comment: str = "",
                    altitude_m: int = 0, speed_kmh: int = 0,
                    course_deg: int = 0) -> str:
    """
    Monta pacote APRS de posição sem timestamp (formato '=').
    Exemplo:
      PU2OZH-10>APMT,TCPIP*:=2313.73S/04555.49W>via Mesh/APRS-GW
    """
    if len(icon) != 2:
        icon = "/>"

    table  = icon[0]
    symbol = icon[1]

    aprs_lat = _lat_to_aprs(lat)
    aprs_lon = _lon_to_aprs(lon)

    # Altitude em pés (padrão APRS)
    alt_ft = int(altitude_m * 3.28084)
    alt_str = f"/A={alt_ft:06d}" if altitude_m > 0 else ""

    body = (f"={aprs_lat}{table}{aprs_lon}{symbol}"
            f"{alt_str}{comment}")

    return f"{callsign}>APMT,TCPIP*:{body}"


def format_message(src: str, dst: str, body: str, msg_id: str) -> str:
    """
    Monta pacote APRS de mensagem direta.
    Exemplo:
      PU2OZH-10>APMT,TCPIP*::PY5XX    :olá{001
    """
    dst_padded = f"{dst:<9}"
    return f"{src}>APMT,TCPIP*::{dst_padded}:{body}{{{msg_id}}}"


def format_ack(src: str, dst: str, msg_id: str) -> str:
    """Monta pacote de ACK APRS."""
    dst_padded = f"{dst:<9}"
    return f"{src}>APMT,TCPIP*::{dst_padded}:ack{msg_id}"


def parse_aprs_message(raw: str) -> dict | None:
    """
    Parseia linha APRS de mensagem recebida do APRS-IS.
    Retorna dict com src, dst, body, msg_id ou None se não for mensagem.
    """
    try:
        # Formato: SRC>PATH::DST    :BODY{MSGID
        if ">APMT" not in raw and ">" not in raw:
            return None
        if "::" not in raw:
            return None

        src  = raw.split(">")[0].strip()
        rest = raw.split("::")[1]
        dst  = rest[:9].strip()
        msg_part = rest[10:]  # após os 9 chars do dst + ':'

        msg_id = None
        if "{" in msg_part:
            body, msg_id = msg_part.rsplit("{", 1)
            msg_id = msg_id.rstrip("}")
        else:
            body = msg_part

        # ACK não é mensagem
        if body.startswith("ack"):
            return {"type": "ack", "src": src, "dst": dst,
                    "msg_id": body[3:].strip()}

        return {"type": "message", "src": src, "dst": dst,
                "body": body.strip(), "msg_id": msg_id}
    except Exception:
        return None
