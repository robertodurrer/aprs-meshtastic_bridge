"""
Etapa 5 — Roteamento de mensagens Meshtastic → APRS.

Formato esperado no Meshtastic (canal APRS dedicado):
    "PY5XX: corpo da mensagem"
    "PU2OZH-4 obrigado pelo teste"   (com ou sem ":")

Regras:
  - Primeira "palavra" da mensagem deve parecer um callsign válido
    (2-6 letras/números, opcional -SSID)
  - Se não houver callsign reconhecível, a mensagem é registrada
    como inválida e NÃO é enviada (evita spam no APRS-IS)
"""
import re
import time
import threading
from typing import Optional

from modules.logger import get_logger
from modules.aprs_format import format_message

log = get_logger("router")

# Regex de callsign APRS: 2-6 chars alfanuméricos + opcional -SSID (1-2 digitos/letra)
CALLSIGN_RE = re.compile(r'^([A-Z0-9]{3,6}(?:-[A-Z0-9]{1,2})?)[:\s]+(.+)$', re.IGNORECASE)

MAX_RETRIES   = 3
RETRY_DELAY_S = 15
ACK_TIMEOUT_S = 30


class MessageRouter:

    def __init__(self, db, aprs_is, mesh_iface=None):
        self.db        = db
        self.aprs_is   = aprs_is
        self.mesh      = mesh_iface
        self._msg_seq  = 0
        self._pending  = {}   # msg_id -> {row_id, retries, dst, packet, ts}
        self._lock     = threading.Lock()

    def _next_msg_id(self) -> str:
        with self._lock:
            self._msg_seq = (self._msg_seq + 1) % 1000
            return f"{self._msg_seq:03d}"

    def parse_destination(self, text: str) -> Optional[tuple]:
        """
        Extrai (callsign_destino, corpo) de uma string de mensagem.
        Retorna None se não conseguir identificar um callsign válido.
        """
        if not text or not isinstance(text, str):
            return None
            
        text = text.strip()
        if len(text) < 5:  # Mínimo: "XX: Y"
            return None
            
        m = CALLSIGN_RE.match(text)
        if not m:
            return None
        dst, body = m.group(1).upper(), m.group(2).strip()
        if not body or len(body) < 1:
            return None
        if len(body) > 67:  # Limite APRS para mensagens
            log.warning(f"Corpo da mensagem truncado de {len(body)} para 67 chars")
            body = body[:67]
        return dst, body

    def handle_mesh_message(self, payload: dict):
        """
        Recebe payload de mensagem do canal APRS do Meshtastic,
        identifica destino e envia para o APRS-IS.
        """
        # Validação do payload
        if not isinstance(payload, dict):
            log.error("Payload inválido recebido")
            return
            
        node_id = payload.get("from_id")
        text = payload.get("text")
        
        if not node_id or not text:
            log.warning("Payload incompleto: faltam from_id ou text")
            return

        op = self.db.get_operator_by_node(node_id)
        if not op:
            log.warning(f"Mensagem de nó não cadastrado ({node_id}) ignorada")
            return
        if not op["tx_aprs"]:
            log.info(f"Mensagem de {op['callsign']} ignorada — tx_aprs=0")
            return

        parsed = self.parse_destination(text)
        if not parsed:
            log.warning(f"Mensagem de {op['callsign']} sem destino "
                       f"reconhecível: '{text[:60]}' — descartada")
            return

        dst_call, body = parsed
        msg_id = self._next_msg_id()

        # Registra no banco como pending
        try:
            row_id = self.db.save_message(
                direction = "mesh_to_aprs",
                src       = op["callsign"],
                dst       = dst_call,
                body      = body,
                msg_id    = msg_id,
                status    = "pending"
            )
        except Exception as e:
            log.error(f"Erro ao salvar mensagem no banco: {e}")
            return

        packet = format_message(op["callsign"], dst_call, body, msg_id)

        if not self.aprs_is.connected:
            log.error(f"APRS-IS offline — mensagem {row_id} fica pending")
            return

        sent = self.aprs_is.send(packet)
        if sent:
            log.info(f"MSG enviada: {op['callsign']} → {dst_call}: "
                     f"'{body[:50]}' (id={msg_id})")
            with self._lock:
                self._pending[msg_id] = {
                    "row_id": row_id, "retries": 0,
                    "dst": dst_call, "packet": packet,
                    "ts": time.time(), "src": op["callsign"],
                    "body": body,
                }
            self.db.touch_operator(op["callsign"])
            threading.Thread(target=self._watch_ack, args=(msg_id,),
                             daemon=True).start()
        else:
            self.db.update_message_status(row_id, "failed")
            log.error(f"Falha ao enviar mensagem {row_id}")

    def _watch_ack(self, msg_id: str):
        """Aguarda ACK; se não chegar, faz retry até MAX_RETRIES."""
        deadline = time.time() + ACK_TIMEOUT_S
        while time.time() < deadline:
            time.sleep(1)
            with self._lock:
                entry = self._pending.get(msg_id)
            if entry is None:
                return  # ACK já recebido (removido pelo handle_ack)

        # Timeout — retry ou falha definitiva
        with self._lock:
            entry = self._pending.get(msg_id)
            if entry is None:
                return
            entry["retries"] += 1

        if entry["retries"] > MAX_RETRIES:
            log.warning(f"Mensagem {msg_id} ({entry['src']}→{entry['dst']}) "
                       f"sem ACK após {MAX_RETRIES} tentativas — FALHA")
            self.db.update_message_status(entry["row_id"], "failed")
            with self._lock:
                self._pending.pop(msg_id, None)
            return

        log.info(f"Retry {entry['retries']}/{MAX_RETRIES} para msg {msg_id}")
        self.aprs_is.send(entry["packet"])
        threading.Thread(target=self._watch_ack, args=(msg_id,),
                         daemon=True).start()

    def handle_ack(self, ack_payload: dict):
        """Chamado quando um ACK chega do APRS-IS."""
        msg_id = ack_payload["msg_id"]
        with self._lock:
            entry = self._pending.pop(msg_id, None)
        if entry:
            self.db.update_message_status(entry["row_id"], "delivered")
            log.info(f"✓ ACK recebido para msg {msg_id} "
                     f"({entry['src']}→{entry['dst']}) — ENTREGUE")

            # Notifica o nó Meshtastic de origem (se a interface existir)
            if self.mesh:
                self.mesh.send_text(
                    f"[APRS] entregue a {entry['dst']}",
                    destination_id="^all",
                    channel_index=None  # usa o canal APRS padrão
                )
        else:
            log.debug(f"ACK para msg_id={msg_id} não encontrado (já processado?)")
