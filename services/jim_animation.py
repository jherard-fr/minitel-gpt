#!/usr/bin/env python3
"""
Animation d'accueil style Minitel — portrait Videotex de Jim.
Effet "élection Mitterrand 1981" : mosaïque 2×3 pixels, drapeau tricolore.
À 1200 baud, chaque ligne prend ~400ms → 22 lignes = ~9s de révélation naturelle.
"""
import time, sys, os

sys.path.insert(0, os.path.dirname(__file__))
from minitel_serial import MinitelSerial

# Données Videotex pré-générées (mosaic + couleurs drapeau)
try:
    from jim_videotex import JIM_VIDEOTEX
    USE_VIDEOTEX = True
except ImportError:
    USE_VIDEOTEX = False
    from jim_ascii import JIM_ASCII

COLS = 40

ESC = 0x1B
SO  = 0x0E
SI  = 0x0F
CR  = 0x0D
LF  = 0x0A
FF  = 0x0C

FG_WHITE  = bytes([ESC, 0x47])
FG_YELLOW = bytes([ESC, 0x43])
BG_BLACK  = bytes([ESC, 0x50])
BG_BLUE   = bytes([ESC, 0x54])


def center(text: str, width: int = COLS) -> str:
    text = text[:width]
    return " " * ((width - len(text)) // 2) + text


def play_mitterrand_intro(m: MinitelSerial):
    """
    Animation complète : portrait Videotex + message d'anniversaire.
    Le baud rate (1200) crée naturellement l'effet de révélation progressive.
    """
    if USE_VIDEOTEX:
        _play_videotex(m)
    else:
        _play_ascii_fallback(m)


def _play_videotex(m: MinitelSerial):
    """Portrait en mosaïque Videotex authentique avec drapeau tricolore."""

    # Titre d'intro en mode texte avant le portrait
    m.send_bytes(bytes([FF]))           # Efface écran
    m.send_bytes(FG_YELLOW)
    titre = center("10 MAI 1981 - SOIREE ELECTORALE")
    m.send_text(titre + "\r\n")
    m.send_text("=" * COLS + "\r\n")
    time.sleep(0.4)

    # ── Portrait Videotex ligne par ligne ─────────────────────────────────
    # On découpe JIM_VIDEOTEX en lignes pour l'animation progressive.
    # Chaque ligne se termine par CR+LF (0x0D 0x0A).
    # À 1200 baud ~120 chars/sec : chaque ligne (~50 octets) ≈ 400ms.
    # On expédie le FF initial et les attributs globaux, puis ligne par ligne.

    lines = []
    current = bytearray()
    i = 0
    data = JIM_VIDEOTEX
    # Sauter le FF et les attributs globaux en tête (avant le premier CR+LF)
    header = bytearray()
    while i < len(data):
        b = data[i]
        if b == LF and current and current[-1] == CR:
            # Fin de première ligne
            lines.append(bytes(current))
            current = bytearray()
        elif b == FF or (b == ESC and i + 1 < len(data) and data[i+1] in (0x40, 0x47)):
            if not lines:
                header.append(b)
                if b == ESC:
                    i += 1
                    header.append(data[i])
            else:
                current.append(b)
        else:
            current.append(b)
        i += 1
    if current:
        lines.append(bytes(current))

    # Envoi du header (FF + attributs globaux + SO)
    m.send_bytes(bytes([FF]))
    m.send_bytes(FG_YELLOW)
    titre = center("10 MAI 1981 - SOIREE ELECTORALE")
    m.send_text(titre + "\r\n")
    m.send_text("=" * COLS + "\r\n")

    # Envoi ligne par ligne — la vitesse série crée l'effet
    m.send_bytes(bytes([SO]))           # Bascule en mode mosaïque
    for line in lines:
        m.send_bytes(line)
        # Petite pause dramatique toutes les 7 lignes
        line_num = lines.index(line)
        if line_num in (6, 13):
            time.sleep(0.2)

    m.send_bytes(bytes([SI]))           # Retour mode texte
    m.send_bytes(FG_WHITE)
    m.send_bytes(BG_BLACK)

    # ── Message d'anniversaire ────────────────────────────────────────────
    m.send_text("=" * COLS + "\r\n")
    time.sleep(0.3)

    label = center("*** BON ANNIVERSAIRE JIM ! ***")
    for char in label:
        m.send_bytes(char.encode("ascii", errors="replace"))
        time.sleep(0.06)
    m.newline()

    m.send_text(center("LES ANNEES 80 TE SALUENT !") + "\r\n")
    time.sleep(0.4)
    m.send_text("=" * COLS + "\r\n")
    m.send_text(center("Appuyez sur ENTREE") + "\r\n")


def _play_ascii_fallback(m: MinitelSerial):
    """Fallback ASCII si le fichier Videotex n'est pas disponible."""
    m.clear_screen()
    m.cursor_home()
    m.send_text("=" * COLS + "\r\n")
    for line in JIM_ASCII:
        m.send_text(line + "\r\n")
    m.send_text("=" * COLS + "\r\n")
    m.send_text(center("*** BON ANNIVERSAIRE JIM ! ***") + "\r\n")
    m.send_text(center("Appuyez sur ENTREE") + "\r\n")


def play_interlude(m: MinitelSerial):
    """Interlude court entre deux questions."""
    if USE_VIDEOTEX:
        m.send_bytes(bytes([FF]))
        m.send_bytes(bytes([SO]))
        m.send_bytes(JIM_VIDEOTEX)
        m.send_bytes(bytes([SI]))
        m.send_bytes(FG_WHITE)
        m.send_bytes(BG_BLACK)
        m.send_text(center("*** BON ANNIVERSAIRE JIM ! ***") + "\r\n")
    else:
        _play_ascii_fallback(m)
    time.sleep(0.3)


if __name__ == "__main__":
    m = MinitelSerial()
    m.open()
    play_mitterrand_intro(m)
    m.close()
