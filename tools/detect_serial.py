#!/usr/bin/env python3
"""
Detecta portas seriais disponíveis e tenta identificar o nó Meshtastic.
Executar ANTES de conectar o nó para ver o estado "sem dispositivo",
depois conectar o nó e rodar novamente para ver a porta nova.

Uso: python tools/detect_serial.py
"""
import sys
import glob
import serial.tools.list_ports

print("\n── Portas seriais disponíveis ────────────────────────")
ports = list(serial.tools.list_ports.comports())
if not ports:
    print("  Nenhuma porta serial encontrada.")
else:
    for p in ports:
        marker = " ◄ provável Meshtastic" if any(
            x in (p.description or "").lower()
            for x in ["cp210", "ch340", "ftdi", "uart", "usb serial", "meshtastic"]
        ) else ""
        print(f"  {p.device:<20} {p.description}{marker}")

print("\n── Dispositivos /dev/tty* relevantes ────────────────")
for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"]:
    for dev in sorted(glob.glob(pattern)):
        print(f"  {dev}")

print("\n── Tentando conexão Meshtastic (auto-detect) ────────")
try:
    import meshtastic.serial_interface
    iface = meshtastic.serial_interface.SerialInterface()
    info = iface.getMyNodeInfo()
    user = info.get("user", {})
    print(f"  ✓ Conectado!")
    print(f"    ID       : {user.get('id','?')}")
    print(f"    Nome     : {user.get('longName','?')}")
    print(f"    Shortname: {user.get('shortName','?')}")
    print(f"    Hardware : {user.get('hwModel','?')}")
    iface.close()
except Exception as e:
    print(f"  ✗ Não conectou: {e}")
    print("    → Verifique se o nó está conectado via USB")
    print("    → Verifique se está no grupo dialout: groups $USER")
print()
