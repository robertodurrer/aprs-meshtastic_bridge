"""
Etapa 3 — Camada de banco de dados (SQLite).
Tabelas: operators, positions, messages
"""
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from modules.logger import get_logger

log = get_logger("database")

class Database:

    def __init__(self, cfg: dict):
        db_path = Path(__file__).parent.parent / cfg["database"]["path"]
        db_path.parent.mkdir(exist_ok=True)
        self.path = str(db_path)
        self._local = threading.local()
        self._init_schema()
        log.info(f"Banco de dados: {self.path}")

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            try:
                self._local.conn = sqlite3.connect(
                    self.path, 
                    check_same_thread=False,
                    timeout=30.0
                )
                self._local.conn.row_factory = sqlite3.Row
                self._local.conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn.execute("PRAGMA foreign_keys=ON")
                self._local.conn.execute("PRAGMA synchronous=NORMAL")
                self._local.conn.execute("PRAGMA cache_size=10000")
            except sqlite3.Error as e:
                log.error(f"Erro ao conectar ao banco de dados: {e}")
                raise
        return self._local.conn

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS operators (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                callsign      TEXT    NOT NULL UNIQUE,
                ssid          TEXT    NOT NULL,
                passcode      INTEGER NOT NULL,
                node_id       TEXT,
                long_name     TEXT,
                short_name    TEXT,
                aprs_icon     TEXT    DEFAULT '/>',
                aprs_comment  TEXT    DEFAULT 'via Mesh/APRS-GW',
                channel_index INTEGER DEFAULT 1,
                pub_position  INTEGER DEFAULT 1,
                rx_aprs       INTEGER DEFAULT 1,
                tx_aprs       INTEGER DEFAULT 1,
                rf_local      INTEGER DEFAULT 0,
                active        INTEGER DEFAULT 1,
                created_at    TEXT    DEFAULT (datetime('now')),
                last_seen     TEXT
            );

            CREATE TABLE IF NOT EXISTS positions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id    TEXT    NOT NULL,
                callsign   TEXT,
                latitude   REAL    NOT NULL,
                longitude  REAL    NOT NULL,
                altitude   INTEGER DEFAULT 0,
                speed      INTEGER DEFAULT 0,
                course     INTEGER DEFAULT 0,
                ts         TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                direction  TEXT    NOT NULL,
                src        TEXT    NOT NULL,
                dst        TEXT    NOT NULL,
                body       TEXT    NOT NULL,
                msg_id     TEXT,
                status     TEXT    DEFAULT 'pending',
                retries    INTEGER DEFAULT 0,
                ts         TEXT    DEFAULT (datetime('now')),
                ts_ack     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_operators_node
                ON operators(node_id);
            CREATE INDEX IF NOT EXISTS idx_positions_node
                ON positions(node_id);
            CREATE INDEX IF NOT EXISTS idx_messages_src
                ON messages(src);
            CREATE INDEX IF NOT EXISTS idx_messages_dst
                ON messages(dst);
        """)
        self.conn.commit()
        log.info("Schema inicializado")

    # ── Operators ─────────────────────────────────────────────
    def add_operator(self, callsign: str, ssid: str, passcode: int,
                     node_id: str = None, long_name: str = "",
                     short_name: str = "", **kwargs) -> bool:
        # Validação de entrada
        if not callsign or not isinstance(callsign, str):
            log.error("Callsign inválido")
            return False
        if not isinstance(passcode, int):
            log.error("Passcode deve ser um número inteiro")
            return False
            
        try:
            with self.conn:  # Transação automática
                self.conn.execute("""
                    INSERT INTO operators
                        (callsign, ssid, passcode, node_id, long_name, short_name,
                         aprs_icon, aprs_comment, channel_index,
                         pub_position, rx_aprs, tx_aprs, rf_local, active)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                """, (
                    callsign.upper(), ssid.upper(), passcode, node_id,
                    long_name[:50], short_name[:10],  # Limita tamanho
                    kwargs.get("aprs_icon", "/>")[:2],
                    kwargs.get("aprs_comment", "via Mesh/APRS-GW")[:100],
                    kwargs.get("channel_index", 1),
                    int(kwargs.get("pub_position", True)),
                    int(kwargs.get("rx_aprs", True)),
                    int(kwargs.get("tx_aprs", True)),
                    int(kwargs.get("rf_local", False)),
                ))
            log.info(f"Operador cadastrado: {callsign} (node={node_id})")
            return True
        except sqlite3.IntegrityError as e:
            log.warning(f"Operador já existe: {callsign} - {e}")
            return False
        except sqlite3.Error as e:
            log.error(f"Erro de banco ao cadastrar operador: {e}")
            return False
        except Exception as e:
            log.error(f"Erro inesperado ao cadastrar operador: {e}")
            return False

    def get_operator_by_callsign(self, callsign: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM operators WHERE callsign=? AND active=1",
            (callsign.upper(),)
        ).fetchone()
        return dict(row) if row else None

    def get_operator_by_node(self, node_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM operators WHERE node_id=? AND active=1",
            (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_operators(self, active_only: bool = True) -> list:
        q = "SELECT * FROM operators"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY callsign"
        rows = self.conn.execute(q).fetchall()
        return [dict(r) for r in rows]

    def update_operator(self, callsign: str, **fields) -> bool:
        allowed = {"node_id","long_name","short_name","aprs_icon",
                   "aprs_comment","pub_position","rx_aprs","tx_aprs",
                   "rf_local","active","last_seen"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        self.conn.execute(
            f"UPDATE operators SET {set_clause} WHERE callsign=?",
            (*updates.values(), callsign.upper())
        )
        self.conn.commit()
        return True

    def remove_operator(self, callsign: str) -> bool:
        self.conn.execute(
            "UPDATE operators SET active=0 WHERE callsign=?",
            (callsign.upper(),)
        )
        self.conn.commit()
        log.info(f"Operador desativado: {callsign}")
        return True

    def touch_operator(self, callsign: str):
        self.conn.execute(
            "UPDATE operators SET last_seen=datetime('now') WHERE callsign=?",
            (callsign.upper(),)
        )
        self.conn.commit()

    # ── Positions ─────────────────────────────────────────────
    def save_position(self, node_id: str, lat: float, lon: float,
                      alt: int = 0, speed: int = 0, course: int = 0,
                      callsign: str = None):
        self.conn.execute("""
            INSERT INTO positions (node_id, callsign, latitude, longitude,
                                   altitude, speed, course)
            VALUES (?,?,?,?,?,?,?)
        """, (node_id, callsign, lat, lon, alt, speed, course))
        self.conn.commit()

    def get_last_position(self, node_id: str) -> Optional[dict]:
        row = self.conn.execute("""
            SELECT * FROM positions WHERE node_id=?
            ORDER BY ts DESC LIMIT 1
        """, (node_id,)).fetchone()
        return dict(row) if row else None

    # ── Messages ──────────────────────────────────────────────
    def save_message(self, direction: str, src: str, dst: str,
                     body: str, msg_id: str = None,
                     status: str = "pending") -> int:
        cur = self.conn.execute("""
            INSERT INTO messages (direction, src, dst, body, msg_id, status)
            VALUES (?,?,?,?,?,?)
        """, (direction, src, dst, body, msg_id, status))
        self.conn.commit()
        return cur.lastrowid

    def update_message_status(self, msg_id: int, status: str,
                               ts_ack: str = None):
        self.conn.execute("""
            UPDATE messages SET status=?, ts_ack=?
            WHERE id=?
        """, (status, ts_ack or datetime.utcnow().isoformat(), msg_id))
        self.conn.commit()

    def list_messages(self, limit: int = 100) -> list:
        try:
            rows = self.conn.execute("""
                SELECT * FROM messages ORDER BY ts DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"Erro ao listar mensagens: {e}")
            return []
