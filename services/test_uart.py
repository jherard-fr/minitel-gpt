#!/usr/bin/env python3
"""Test UART autonome - loopback et diagnostic complet."""

import serial
import time
import sys

PORT = "/dev/ttyAMA0"
BAUD = 1200


def check_port():
    import os
    for port in ["/dev/ttyAMA0", "/dev/serial0", "/dev/ttyS0"]:
        exists = os.path.exists(port)
        try:
            target = os.readlink(port) if os.path.islink(port) else port
        except Exception:
            target = port
        print(f"  {port}: {'OK' if exists else 'manquant'} -> {target}")


def loopback_test(port: str, baud: int):
    print(f"\n[TEST LOOPBACK] {port} @ {baud} baud")
    print("  Branchez un pont entre TX (pin8) et RX (pin10) avant de continuer.")
    input("  Appuyez sur Entrée quand le pont est en place... ")

    try:
        ser = serial.Serial(
            port=port, baudrate=baud,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0
        )
    except Exception as e:
        print(f"  ERREUR ouverture port : {e}")
        return False

    test = b"LOOPBACK123\r\n"
    ser.write(test)
    time.sleep(0.5)
    received = ser.read(len(test))
    ser.close()

    if received == test:
        print(f"  SUCCES : recu={repr(received)}")
        return True
    else:
        print(f"  ECHEC  : envoye={repr(test)}, recu={repr(received)}")
        return False


def minitel_ping(port: str, baud: int):
    """Envoie une séquence d'initialisation Minitel et écoute."""
    print(f"\n[TEST MINITEL] Envoi init sur {port} @ {baud} baud")
    try:
        ser = serial.Serial(
            port=port, baudrate=baud,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=3.0
        )
    except Exception as e:
        print(f"  ERREUR : {e}")
        return

    # Effacer écran + texte de test
    ser.write(b"\x0C")  # FF
    time.sleep(0.2)
    ser.write(b"MINITEL GPT - TEST\r\n")
    time.sleep(1.0)

    received = ser.read(64)
    if received:
        print(f"  Recu depuis Minitel : {repr(received)}")
    else:
        print("  Rien recu du Minitel (normal si pas de saisie clavier)")

    ser.close()


if __name__ == "__main__":
    print("=== DIAGNOSTIC UART MINITEL ===\n")
    print("[1] Ports disponibles :")
    check_port()

    port = PORT
    baud = BAUD

    if "--loopback" in sys.argv:
        ok = loopback_test(port, baud)
        sys.exit(0 if ok else 1)
    elif "--minitel" in sys.argv:
        minitel_ping(port, baud)
    else:
        print("\nUsage:")
        print("  python3 test_uart.py --loopback   (pont TX-RX requis)")
        print("  python3 test_uart.py --minitel    (Minitel branché requis)")
