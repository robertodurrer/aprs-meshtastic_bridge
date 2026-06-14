"""
Etapa 4 — Handler de posição: Meshtastic → APRS-IS.
Recebe payload de posição, consulta o banco, formata e envia.
"""
from modules.logger import get_logger
from modules.aprs_format import format_position

log = get_logger("position")


class PositionHandler:

    def __init__(self, db, aprs_is):
        self.db      = db
        self.aprs_is = aprs_is

    def handle(self, payload: dict):
        """
        Recebe payload de posição do MeshtasticInterface e publica no APRS-IS
        se o operador estiver cadastrado e com pub_position=1.
        """
        node_id = payload["from_id"]
        lat     = payload["latitude"]
        lon     = payload["longitude"]
        alt     = payload.get("altitude", 0)
        speed   = payload.get("speed", 0)
        course  = payload.get("course", 0)

        # Busca operador cadastrado para este nó
        op = self.db.get_operator_by_node(node_id)
        if not op:
            log.debug(f"Posição de {node_id} ignorada — nó não cadastrado")
            return

        if not op["pub_position"]:
            log.debug(f"Posição de {op['callsign']} ignorada — pub_position=0")
            return

        if not self.aprs_is.connected:
            log.warning(f"Posição de {op['callsign']} descartada — APRS-IS offline")
            return

        # Salva no banco
        self.db.save_position(node_id, lat, lon, alt, speed, course,
                              callsign=op["callsign"])
        self.db.touch_operator(op["callsign"])

        # Formata e envia
        packet = format_position(
            callsign  = op["callsign"],
            lat       = lat,
            lon       = lon,
            icon      = op.get("aprs_icon", "/>"),
            comment   = op.get("aprs_comment", "via Mesh/APRS-GW"),
            altitude_m= alt,
            speed_kmh = speed,
            course_deg= course,
        )

        sent = self.aprs_is.send(packet)
        if sent:
            log.info(f"Posição publicada: {op['callsign']} "
                     f"→ {lat:.5f},{lon:.5f} alt={alt}m")
        else:
            log.error(f"Falha ao publicar posição de {op['callsign']}")
