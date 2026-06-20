"""
Etapa 4 — Conexão persistente com o APRS-IS.
Gerencia login, envio, recepção e reconexão automática.
"""
import socket
import threading
import time
from typing import Callable, Optional

from modules.logger import get_logger

log = get_logger("aprs_is")

KEEPALIVE_INTERVAL = 120   # segundos entre heartbeats
RECONNECT_DELAY    = 30    # segundos antes de tentar reconectar
RECV_TIMEOUT       = 5     # timeout de leitura (não bloqueia para sempre)


class APRSISConnection:

    def __init__(self, cfg: dict):
        gw = cfg["gateway"]
        self.host      = gw["aprs_is_host"]
        self.port      = gw["aprs_is_port"]
        self.callsign  = gw["callsign"]
        self.passcode  = gw["passcode"]
        self.filter    = gw.get("aprs_is_filter", "m/50")

        self._sock: Optional[socket.socket] = None
        self._running  = False
        self._lock     = threading.Lock()
        self._on_packet: Optional[Callable] = None

    def on_packet(self, fn: Callable):
        """Registra callback para pacotes recebidos do APRS-IS."""
        self._on_packet = fn

    # ── Conexão ───────────────────────────────────────────────
    def connect(self) -> bool:
        try:
            log.info(f"Conectando ao APRS-IS {self.host}:{self.port}...")
            sock = socket.create_connection((self.host, self.port), timeout=15)
            sock.settimeout(RECV_TIMEOUT)

            # Lê banner
            banner = sock.recv(512).decode("ascii", errors="ignore")
            log.debug(f"Banner: {banner.strip()}")

            # Validação básica do banner
            if not banner or "aprsc" not in banner.lower():
                log.warning(f"Banner suspeito do servidor: {banner.strip()}")

            # Login
            login = (f"user {self.callsign} pass {self.passcode} "
                     f"vers MeshAPRS-GW 0.1 filter {self.filter}\r\n")
            sock.send(login.encode("ascii", errors="replace"))

            # Confirma login
            resp = sock.recv(512).decode("ascii", errors="ignore")
            log.debug(f"Login resp: {resp.strip()}")

            if "unverified" in resp.lower():
                log.error(f"APRS-IS rejeitou login: {resp.strip()}")
                sock.close()
                return False
            
            if "logresp" not in resp.lower():
                log.warning(f"Resposta de login inesperada: {resp.strip()}")

            with self._lock:
                self._sock = sock

            log.info(f"APRS-IS conectado como {self.callsign}")
            return True

        except socket.timeout:
            log.error("Timeout ao conectar ao APRS-IS")
            return False
        except socket.gaierror as e:
            log.error(f"Erro de DNS ao conectar ao APRS-IS: {e}")
            return False
        except ConnectionRefusedError:
            log.error("Conexão recusada pelo servidor APRS-IS")
            return False
        except Exception as e:
            log.error(f"Falha ao conectar APRS-IS: {e}")
            return False

    def _reconnect_loop(self):
        while self._running:
            time.sleep(RECONNECT_DELAY)
            log.info("Tentando reconectar ao APRS-IS...")
            if self.connect():
                # Reinicia thread de recepção
                threading.Thread(target=self._recv_loop,
                                 daemon=True, name="aprs-recv").start()
                return

    # ── Envio ─────────────────────────────────────────────────
    def send(self, packet: str) -> bool:
        if not packet.endswith("\r\n"):
            packet += "\r\n"
        with self._lock:
            if not self._sock:
                log.warning("send() sem conexão ativa")
                return False
            try:
                self._sock.send(packet.encode("ascii", errors="replace"))
                log.info(f"TX → APRS-IS: {packet.strip()}")
                return True
            except Exception as e:
                log.error(f"Erro ao enviar para APRS-IS: {e}")
                self._sock = None
                return False

    # ── Recepção ──────────────────────────────────────────────
    def _recv_loop(self):
        buf = ""
        while self._running:
            with self._lock:
                sock = self._sock
            if not sock:
                time.sleep(1)
                continue
            try:
                data = sock.recv(4096).decode("ascii", errors="ignore")
                if not data:
                    raise ConnectionResetError("Conexão fechada pelo servidor")
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line and not line.startswith("#"):
                        log.debug(f"RX ← APRS-IS: {line}")
                        if self._on_packet:
                            self._on_packet(line)
            except socket.timeout:
                continue
            except Exception as e:
                log.warning(f"Conexão APRS-IS perdida: {e}")
                with self._lock:
                    self._sock = None
                if self._running:
                    threading.Thread(target=self._reconnect_loop,
                                     daemon=True, name="aprs-recon").start()
                break

    # ── Keepalive ─────────────────────────────────────────────
    def _keepalive_loop(self):
        while self._running:
            time.sleep(KEEPALIVE_INTERVAL)
            self.send(f"# MeshAPRS-GW keepalive {self.callsign}")

    # ── Lifecycle ─────────────────────────────────────────────
    def start(self):
        self._running = True
        if self.connect():
            threading.Thread(target=self._recv_loop,
                             daemon=True, name="aprs-recv").start()
            threading.Thread(target=self._keepalive_loop,
                             daemon=True, name="aprs-keepalive").start()
        else:
            threading.Thread(target=self._reconnect_loop,
                             daemon=True, name="aprs-recon").start()

    def stop(self):
        self._running = False
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
        log.info("Conexão APRS-IS encerrada")

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._sock is not None
