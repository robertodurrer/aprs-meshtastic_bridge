#!/usr/bin/env python3
"""
CLI de gerenciamento do Mesh↔APRS Gateway.

Uso:
  python manage.py list
  python manage.py add PU2OZH-10 --passcode 19376 --node !f714909c --nome "Roberto"
  python manage.py info PU2OZH-10
  python manage.py enable  PU2OZH-10
  python manage.py disable PU2OZH-10
  python manage.py remove  PU2OZH-10
  python manage.py validate PU2OZH --passcode 19376
  python manage.py messages [--limit N]
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config_loader import load as load_config
from modules.database import Database
from modules.aprs_auth import validate_with_aprs_is, calc_passcode, suggest_ssid
from modules.logger import get_logger

log = get_logger("manage")
cfg = load_config()
db  = Database(cfg)

# ── Cores ─────────────────────────────────────────────────────
G = '\033[32m'; R = '\033[31m'; Y = '\033[33m'; B = '\033[34m'; N = '\033[0m'

def cmd_list(args):
    ops = db.list_operators(active_only=not args.todos)
    if not ops:
        print(f"  {Y}Nenhum operador cadastrado.{N}")
        print(f"  Use: python manage.py add <CALLSIGN> --passcode <PASSCODE>")
        return
    print(f"\n{'CALLSIGN':<14} {'NODE ID':<14} {'SHORTNAME':<10} "
          f"{'POS':>4} {'RX':>4} {'TX':>4} {'ATIVO':>6}  ÚLTIMO CONTATO")
    print("─" * 80)
    for op in ops:
        ativo  = f"{G}sim{N}" if op["active"] else f"{R}não{N}"
        pos    = f"{G}✓{N}" if op["pub_position"] else f"{R}✗{N}"
        rx     = f"{G}✓{N}" if op["rx_aprs"]     else f"{R}✗{N}"
        tx     = f"{G}✓{N}" if op["tx_aprs"]     else f"{R}✗{N}"
        node   = op["node_id"] or "—"
        short  = op["short_name"] or "—"
        last   = (op["last_seen"] or "nunca")[:16]
        print(f"  {op['callsign']:<12} {node:<14} {short:<10} "
              f"{pos:>4} {rx:>4} {tx:>4} {ativo:>6}  {last}")
    print()

def cmd_add(args):
    callsign = args.callsign.upper()
    passcode = args.passcode

    print(f"\n  Validando {callsign} / {passcode}...")
    ok, msg = validate_with_aprs_is(callsign, passcode)
    if not ok:
        print(f"  {R}✗ {msg}{N}")
        sys.exit(1)
    print(f"  {G}✓ {msg}{N}")

    # Sugerir SSID se não tiver
    existing = [op["callsign"] for op in db.list_operators(active_only=False)]
    base = callsign.split("-")[0]
    if "-" not in callsign:
        ssid = suggest_ssid(base, existing)
        print(f"  {Y}SSID sugerido: {ssid} (use --callsign {ssid} para especificar){N}")
        callsign = ssid

    ok = db.add_operator(
        callsign  = callsign,
        ssid      = callsign,
        passcode  = passcode,
        node_id   = args.node,
        long_name = args.nome or "",
        short_name= args.short or callsign.split("-")[0][-4:],
        aprs_icon = args.icone or "/>",
        aprs_comment = args.comment or "via Mesh/APRS-GW",
    )
    if ok:
        print(f"  {G}✓ Operador {callsign} cadastrado com sucesso!{N}\n")
    else:
        print(f"  {R}✗ Já existe um operador com este callsign.{N}\n")
        sys.exit(1)

def cmd_info(args):
    op = db.get_operator_by_callsign(args.callsign)
    if not op:
        print(f"  {R}Operador não encontrado: {args.callsign}{N}")
        sys.exit(1)
    print(f"\n── {op['callsign']} ──────────────────────────────────")
    for k, v in op.items():
        if k == "passcode":
            v = "●●●●●"
        print(f"  {k:<16}: {v}")
    print()

def cmd_enable(args):
    db.update_operator(args.callsign, active=1)
    print(f"  {G}✓ {args.callsign} ativado{N}")

def cmd_disable(args):
    db.update_operator(args.callsign, active=0)
    print(f"  {Y}⚠ {args.callsign} desativado{N}")

def cmd_remove(args):
    confirm = input(f"  Remover {args.callsign}? (s/N): ")
    if confirm.lower() == "s":
        db.remove_operator(args.callsign)
        print(f"  {G}✓ {args.callsign} removido{N}")
    else:
        print("  Cancelado.")

def cmd_validate(args):
    ok, msg = validate_with_aprs_is(args.callsign, args.passcode)
    calc = calc_passcode(args.callsign)
    print(f"\n  Indicativo : {args.callsign}")
    print(f"  Informado  : {args.passcode}")
    print(f"  Calculado  : {calc}")
    print(f"  Resultado  : {(G+'✓ '+N) if ok else (R+'✗ '+N)}{msg}\n")

def cmd_messages(args):
    msgs = db.list_messages(limit=args.limit)
    if not msgs:
        print("  Nenhuma mensagem registrada.")
        return
    print(f"\n{'TS':<18} {'DIR':<10} {'DE':<14} {'PARA':<14} {'STATUS':<10} MENSAGEM")
    print("─" * 90)
    for m in msgs:
        ts    = m["ts"][:16]
        direc = f"{B}M→A{N}" if m["direction"]=="mesh_to_aprs" else f"{Y}A→M{N}"
        print(f"  {ts}  {direc}  {m['src']:<14} {m['dst']:<14} "
              f"{m['status']:<10} {m['body'][:40]}")
    print()

# ── Parser ────────────────────────────────────────────────────
parser = argparse.ArgumentParser(prog="manage.py")
sub = parser.add_subparsers(dest="cmd")

p_list = sub.add_parser("list", help="Listar operadores")
p_list.add_argument("--todos", action="store_true", help="Incluir inativos")

p_add = sub.add_parser("add", help="Cadastrar operador")
p_add.add_argument("callsign")
p_add.add_argument("--passcode", type=int, required=True)
p_add.add_argument("--node",    help="Node ID Meshtastic (ex: !f714909c)")
p_add.add_argument("--nome",    help="Nome completo")
p_add.add_argument("--short",   help="Shortname (4 chars)")
p_add.add_argument("--icone",   help="Ícone APRS (ex: />)")
p_add.add_argument("--comment", help="Comentário do beacon")

p_info = sub.add_parser("info", help="Ver detalhes de operador")
p_info.add_argument("callsign")

p_en = sub.add_parser("enable",  help="Ativar operador")
p_en.add_argument("callsign")

p_dis = sub.add_parser("disable", help="Desativar operador")
p_dis.add_argument("callsign")

p_rem = sub.add_parser("remove",  help="Remover operador")
p_rem.add_argument("callsign")

p_val = sub.add_parser("validate", help="Validar callsign/passcode")
p_val.add_argument("callsign")
p_val.add_argument("--passcode", type=int, required=True)

p_msg = sub.add_parser("messages", help="Ver log de mensagens")
p_msg.add_argument("--limit", type=int, default=50)

args = parser.parse_args()
cmds = {
    "list": cmd_list, "add": cmd_add, "info": cmd_info,
    "enable": cmd_enable, "disable": cmd_disable, "remove": cmd_remove,
    "validate": cmd_validate, "messages": cmd_messages,
}
if args.cmd in cmds:
    cmds[args.cmd](args)
else:
    parser.print_help()
