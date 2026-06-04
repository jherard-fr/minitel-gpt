#!/usr/bin/env python3
"""
Génère un portrait en mosaïque Videotex (standard Minitel) depuis jim2.jpg.

Principe :
  Chaque caractère Minitel en mode mosaïque G1 encode une cellule 2×3 pixels.
  Résolution effective : 40 chars × 22 lignes = 80×66 "pixels" mosaïque.
  Fond : drapeau tricolore (bleu / blanc / rouge).
  Portrait : pixels noirs sur fond coloré (exact effet Mitterrand 1981).

Encodage Videotex mosaïque :
  Pixel layout dans une cellule :   p0 p1
                                    p2 p3
                                    p4 p5
  Si p5 = 0 : code = 0x20 + (p0 + p1*2 + p2*4 + p3*8 + p4*16)  → 0x20-0x3F
  Si p5 = 1 : code = 0x60 + (p0 + p1*2 + p2*4 + p3*8 + p4*16)  → 0x60-0x7F
  (la plage 0x40-0x5F est évitée car elle correspond aux lettres G0)
"""
import os, sys
try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow",
                           "--break-system-packages", "-q"])
    from PIL import Image, ImageEnhance, ImageOps

IMG_PATH = os.path.join(os.path.dirname(__file__), "..", "jim2.jpg")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "services", "jim_videotex.py")

# ── Dimensions ──────────────────────────────────────────────────────────────
# 40 colonnes totales dont 3 occupées par les attributs couleur (1 par zone)
# → 37 colonnes mosaïque effectives = 74 pixels de large
ROWS        = 22          # lignes portrait
MOSAIC_COLS = 37          # colonnes mosaïque (portrait)
ZONE_BLUE   = 12          # colonnes bleues
ZONE_WHITE  = 13          # colonnes blanches
ZONE_RED    = 12          # colonnes rouges   (12+13+12 = 37)

# ── Codes Videotex ──────────────────────────────────────────────────────────
ESC = 0x1B
SO  = 0x0E   # G1 : mode mosaïque
SI  = 0x0F   # G0 : mode texte
CR  = 0x0D
LF  = 0x0A
FF  = 0x0C   # Efface écran + home

FG_BLACK  = (ESC, 0x40)
FG_WHITE  = (ESC, 0x47)
BG_BLACK  = (ESC, 0x50)
BG_RED    = (ESC, 0x51)
BG_BLUE   = (ESC, 0x54)
BG_WHITE  = (ESC, 0x57)

THRESHOLD = 128   # seuil après dithering (image 1-bit convertie : 0 ou 255)


def mosaic_char(p0, p1, p2, p3, p4, p5) -> int:
    bits = p0 + p1*2 + p2*4 + p3*8 + p4*16
    return (0x60 if p5 else 0x20) + bits


def get_pixel_bool(img, x, y) -> bool:
    """True = pixel sombre = appartient au portrait."""
    w, h = img.size
    x = min(x, w - 1)
    y = min(y, h - 1)
    return img.getpixel((x, y)) < THRESHOLD


def build_portrait_row(img, row, col_offset, num_cols) -> bytearray:
    """Construit les octets mosaïque pour une zone de colonnes sur une ligne."""
    buf = bytearray()
    for col in range(num_cols):
        x = (col_offset + col) * 2
        y = row * 3
        p = [get_pixel_bool(img, x + dx, y + dy)
             for dy in range(3) for dx in range(2)]
        # p = [p00, p10, p01, p11, p02, p12]
        buf.append(mosaic_char(p[0], p[1], p[2], p[3], p[4], p[5]))
    return buf


def image_to_videotex(path: str) -> bytes:
    img = Image.open(path).convert("L")

    # Légère accentuation de netteté
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = ImageEnhance.Contrast(img).enhance(1.3)

    # Redimensionner aux dimensions mosaïque AVANT le tramage (plus précis)
    img = img.resize((MOSAIC_COLS * 2, ROWS * 3), Image.LANCZOS)

    # Tramage Floyd-Steinberg (dithering) — distribue l'erreur de quantification
    # comme les vraies images Minitel de l'époque. Rendu beaucoup plus naturel
    # qu'un seuil simple : les demi-tons de la peau et de la barbe sont préservés.
    img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG).convert("L")

    out = bytearray()
    out.append(FF)            # Efface écran
    out.extend(FG_BLACK)      # Foreground noir (pixels portrait)
    out.append(SO)            # Bascule en mode mosaïque G1

    for row in range(ROWS):
        # Zone bleue (attribut occupe 1 position)
        out.extend(BG_BLUE)
        out.extend(build_portrait_row(img, row, 0, ZONE_BLUE))

        # Zone blanche
        out.extend(BG_WHITE)
        out.extend(build_portrait_row(img, row, ZONE_BLUE, ZONE_WHITE))

        # Zone rouge
        out.extend(BG_RED)
        out.extend(build_portrait_row(img, row, ZONE_BLUE + ZONE_WHITE, ZONE_RED))

        out.extend([CR, LF])

    out.append(SI)            # Retour mode texte G0
    out.extend(FG_WHITE)      # Foreground blanc pour le texte qui suit
    out.extend(BG_BLACK)      # Fond noir pour le texte

    return bytes(out)


def preview(data: bytes):
    """Aperçu ASCII approché des données Videotex."""
    SHADE = "@#*+:- "
    row = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == ESC:
            i += 2; continue
        if b in (SO, SI, FF, CR):
            i += 1; continue
        if b == LF:
            print("".join(row)); row = []; i += 1; continue
        if 0x20 <= b <= 0x3F:
            bits = b - 0x20
        elif 0x60 <= b <= 0x7F:
            bits = (b - 0x60) + 32
        else:
            row.append(' '); i += 1; continue
        density = bin(bits).count('1')
        row.append(SHADE[int(density / 6 * (len(SHADE) - 1))])
        i += 1
    if row:
        print("".join(row))


def main():
    print(f"Génération portrait Videotex depuis {IMG_PATH}...")
    data = image_to_videotex(IMG_PATH)

    print(f"\nAperçu (mosaïque → densité ASCII) :")
    print("=" * MOSAIC_COLS)
    preview(data)
    print("=" * MOSAIC_COLS)
    print(f"\nTaille : {len(data)} octets")

    hex_data = ", ".join(f"0x{b:02x}" for b in data)
    content = f'''# Auto-généré par generate_videotex.py — portrait Videotex Minitel de Jim
# Mosaïque 2×3 standard Videotex, fond drapeau français
# {len(data)} octets / {MOSAIC_COLS}×{ROWS} chars mosaïque = {MOSAIC_COLS*2}×{ROWS*3} pixels
JIM_VIDEOTEX = bytes([{hex_data}])
'''
    with open(OUT_PATH, "w") as f:
        f.write(content)
    print(f"Fichier généré : {OUT_PATH}")


if __name__ == "__main__":
    main()
