"""
Etapa 2 — Interface com o nó Meshtastic.
"""
import time
import threading
from typing import Callable, Optional

import meshtastic
import meshtastic.serial_interface
import meshtastic.ble_interface
from pubsub import pub

from modules.logger import get_logger

log = get_logger("meshtastic")

class MeshtasticInterface:

    def __init__(self, cfg: dict):
        self.cfg = cfg["meshtastic"]
        self.aprs_channel = self.cfg["aprs_channel_index"]
        self.reconnect_interval = self.cfg.get("reconnect_interval_s", 30)
        self.iface = None
        self._running = False
        self._lock = threading.Lock()
        self._on_position = None
        self._on_message = None
        self._on_node_update = None

    def on_position(self, fn: Callable):
        self._on_position = fn

    def on_message(self, fn: Callable):
        self._on_message = fn

    def on_node_update(self, fn: Callable):
        self._on_node_update = fn

    def connect(self) -> bool:
        mode = self.cfg.get("connection", "serial")
        port = self.cfg.get("serial_port", "auto")
        try:
            if mode == "serial":
                kwargs = {} if port == "auto" else {"devPath": port}
                self.iface = meshtastic.serial_interface.SerialInterface(**kwargs)
            elif mode == "ble":
                addr = self.cfg.get("ble_address")
                self.iface = meshtastic.ble_interface.BLEInterface(addr)
            else:
                log.error(f"Modo de conexão desconhecido: {mode}")
                return False

            pub.subscribe(self._receive, "meshtastic.receive")
            pub.subscribe(self._on_connect_cb, "meshtastic.connection.established")
            pub.subscribe(self._on_disconnect_cb, "meshtastic.connection.lost")

            log.info(f"Conectado ao nó Meshtastic via {mode.upper()}")
            self._log_node_info()
            return True

        except Exception as e:
            log.error(f"Falha ao conectar ao nó Meshtastic: {e}")
            return False

    def _on_connect_cb(self, interface, topic=pub.AUTO_TOPIC):
        log.info("Nó Meshtastic: conexão estabelecida")

    def _on_disconnect_cb(self, interface, topic=pub.AUTO_TOPIC):
        log.warning("Nó Meshtastic: conexão perdida")
        if self._running:
            threading.Thread(target=self._reconnect_loop, daemon=True).start()

    def _reconnect_loop(self):
        log.info(f"Tentando reconectar em {self.reconnect_interval}s...")
        while self._running:
            time.sleep(self.reconnect_interval)
            if self.connect():
                log.info("Reconexão bem-sucedida")
                return
            log.warning("Reconexão falhou, tentando novamente...")

    def _log_node_info(self):
        try:
            info = self.iface.getMyNodeInfo()
            node_id = info.get("user", {}).get("id", "?")
            name    = info.get("user", {}).get("longName", "?")
            short   = info.get("user", {}).get("shortName", "?")
            hw      = info.get("user", {}).get("hwModel", "?")
            log.info(f"Nó local: {name} ({short}) | ID: {node_id} | HW: {hw}")
        except Exception as e:
            log.warning(f"Não foi possível ler info do nó: {e}")

    def _receive(self, packet: dict, interface):
        try:
            channel = packet.get("channel", 0)
            decoded = packet.get("decoded", {})
            portnum = decoded.get("portnum", "")
            from_id = packet.get("fromId", "?")
            to_id   = packet.get("toId", "^all")

            log.debug(f"PKT ch={channel} from={from_id} to={to_id} port={portnum}")

            if portnum == "POSITION_APP":
                pos = decoded.get("position", {})
                if pos and self._on_position:
                    payload = {
                        "from_id":   from_id,
                        "to_id":     to_id,
                        "channel":   channel,
                        "latitude":  pos.get("latitudeI", 0) / 1e7,
                        "longitude": pos.get("longitudeI", 0) / 1e7,
                        "altitude":  pos.get("altitude", 0),
                        "speed":     pos.get("groundSpeed", 0),
                        "course":    pos.get("groundTrack", 0),
                        "timestamp": pos.get("time", 0),
                        "raw":       packet,
                    }
                    if payload["latitude"] != 0 or payload["longitude"] != 0:
                        log.info(f"POSIÇÃO de {from_id}: "
                                 f"{payload['latitude']:.5f},{payload['longitude']:.5f} "
                                 f"alt={payload['altitude']}m ch={channel}")
                        self._on_position(payload)

            elif portnum == "TEXT_MESSAGE_APP":
                text = decoded.get("text", "")
                if self._on_message:
                    payload = {
                        "from_id":  from_id,
                        "to_id":    to_id,
                        "channel":  channel,
                        "text":     text,
                        "raw":      packet,
                    }
                    if channel == self.aprs_channel:
                        log.info(f"MSG APRS-CH de {from_id}: '{text[:60]}'")
                        self._on_message(payload)
                    else:
                        log.debug(f"MSG ignorada (ch={channel}, esperado ch={self.aprs_channel})")

            elif portnum == "NODEINFO_APP":
                if self._on_node_update:
                    user = decoded.get("user", {})
                    payload = {
                        "from_id":    from_id,
                        "long_name":  user.get("longName", ""),
                        "short_name": user.get("shortName", ""),
                        "hw_model":   user.get("hwModel", ""),
                        "raw":        packet,
                    }
                    log.debug(f"NODEINFO de {from_id}: {user.get('longName','?')}")
                    self._on_node_update(payload)

        except Exception as e:
            log.error(f"Erro ao processar pacote: {e}", exc_info=True)

    def send_text(self, text: str, destination_id: str = "^all",
                  channel_index: int = None) -> bool:
        ch = channel_index if channel_index is not None else self.aprs_channel
        try:
            self.iface.sendText(text, destinationId=destination_id, channelIndex=ch)
            log.info(f"MSG enviada para {destination_id} ch={ch}: '{text[:60]}'")
            return True
        except Exception as e:
            log.error(f"Erro ao enviar mensagem: {e}")
            return False

    def get_nodes(self) -> dict:
        try:
            return self.iface.nodes or {}
        except Exception:
            return {}

    def start(self):
        self._running = True
        if not self.connect():
            log.warning("Conexão inicial falhou — iniciando loop de reconexão")
            threading.Thread(target=self._reconnect_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self.iface:
            try:
                self.iface.close()
                log.info("Conexão Meshtastic encerrada")
            except Exception:
                pass
