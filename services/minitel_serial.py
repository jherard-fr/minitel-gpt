#!/usr/bin/env python3
"""Service UART Minitel - gère la communication série avec le Minitel Telic MB1."""

import serial
import time
import logging
import sys
from pathlib import Path

# Minitel : 1200 baud, 7 bits, parité paire, 1 stop bit (norme Videotex)
# Détection automatique : FTDI (ttyUSB0) prioritaire sur GPIO UART (ttyAMA0)
import os as _os
def _detect_port() -> str:
    for p in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyAMA0", "/dev/serial0"]:
        if _os.path.exists(p):
            return p
    return "/dev/ttyAMA0"

SERIAL_PORT = _detect_port()
BAUD_RATE = 1200
BYTESIZE = serial.SEVENBITS
PARITY = serial.PARITY_EVEN
STOPBITS = serial.STOPBITS_ONE
TIMEOUT = 0.1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [minitel-serial] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/minitel/minitel-gpt/logs/serial.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


class MinitelSerial:
    def __init__(self):
        self.ser = None

    def open(self):
        self.ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT,
        )
        log.info(f"Port ouvert : {SERIAL_PORT} @ {BAUD_RATE} baud")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            log.info("Port fermé")

    def send_text(self, text: str):
        """Envoie du texte ASCII (converti en Videotex basique)."""
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Port série non ouvert")
        encoded = text.encode("ascii", errors="replace")
        self.ser.write(encoded)
        log.debug(f"Envoyé : {repr(text)}")

    def send_bytes(self, data: bytes):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Port série non ouvert")
        self.ser.write(data)

    def read_char(self) -> str | None:
        """Lit un caractère depuis le Minitel (non bloquant)."""
        if not self.ser or not self.ser.is_open:
            return None
        raw = self.ser.read(1)
        if raw:
            char = raw.decode("ascii", errors="replace")
            log.debug(f"Reçu : {repr(char)} (0x{raw[0]:02x})")
            return char
        return None

    def read_line(self, echo: bool = True, timeout: float = 30.0) -> str:
        """Lit une ligne saisie au clavier Minitel jusqu'à Entrée."""
        buf = []
        start = time.time()
        while time.time() - start < timeout:
            char = self.read_char()
            if char is None:
                continue
            code = ord(char)
            if code == 0x0D:  # Entrée
                if echo:
                    self.send_bytes(b"\r\n")
                return "".join(buf)
            elif code == 0x7F or code == 0x08:  # Retour arrière
                if buf:
                    buf.pop()
                    if echo:
                        self.send_bytes(b"\x08 \x08")
            elif 0x20 <= code <= 0x7E:
                buf.append(char)
                if echo:
                    self.send_bytes(raw := char.encode("ascii"))
        return "".join(buf)

    # --- Séquences Videotex utilitaires ---
    def clear_screen(self):
        self.send_bytes(b"\x0C")  # FF = efface écran Minitel

    def cursor_home(self):
        self.send_bytes(b"\x1E")  # RS = curseur en haut à gauche

    def set_color(self, fg: int = 7):
        """Couleur texte Videotex 0-7."""
        self.send_bytes(bytes([0x1B, 0x40 + fg]))

    def newline(self):
        self.send_bytes(b"\r\n")


def loopback_test():
    """Test loopback : envoie des caractères et vérifie l'écho."""
    log.info("=== TEST LOOPBACK ===")
    ser = serial.Serial(
        port=SERIAL_PORT, baudrate=BAUD_RATE,
        bytesize=BYTESIZE, parity=PARITY,
        stopbits=STOPBITS, timeout=2.0
    )
    test_bytes = b"Hello Minitel!\r\n"
    ser.write(test_bytes)
    time.sleep(0.5)
    received = ser.read(len(test_bytes))
    ser.close()
    if received == test_bytes:
        log.info(f"LOOPBACK OK : {repr(received)}")
        return True
    else:
        log.error(f"LOOPBACK FAIL - envoyé: {repr(test_bytes)}, reçu: {repr(received)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loopback":
        success = loopback_test()
        sys.exit(0 if success else 1)

    m = MinitelSerial()
    m.open()
    m.clear_screen()
    m.cursor_home()
    m.send_text("*** Minitel GPT ***\r\n")
    m.send_text("Connexion OK\r\n")
    m.close()
