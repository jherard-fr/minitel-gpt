#!/usr/bin/env python3
"""
Convertit jim.jpg en ASCII art 40 colonnes pour Minitel.
v2 — zoom sur le visage + contraste amélioré
"""
import sys, os
try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow",
                           "--break-system-packages", "-q"])
    from PIL import Image, ImageEnhance, ImageFilter

IMG_PATH = os.path.join(os.path.dirname(__file__), "..", "jim.jpg")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "services", "jim_ascii.py")

COLS = 40
ROWS = 22

# Palette plus riche : 14 niveaux du plus sombre au plus clair
# Les caractères denses = zones sombres (barbe, lunettes, casquette)
# Les caractères légers = zones claires (peau, ciel)
CHARS = "@#MW8Boar*+=- ."

def brightness_to_char(b: int) -> str:
    idx = int(b / 255 * (len(CHARS) - 1))
    return CHARS[idx]

def image_to_ascii(path: str, cols: int, rows: int) -> list[str]:
    img = Image.open(path).convert("RGB")
    w, h = img.size

    # ── Zoom sur le visage ────────────────────────────────────────────────
    # La photo est un selfie portrait : le visage occupe toute la hauteur.
    # On coupe ~8% en haut (ciel pur) et ~5% en bas (épaules/sac)
    # et on resserre horizontalement pour centrer le visage.
    crop = img.crop((
        int(w * 0.05),   # gauche : couper le bord
        int(h * 0.00),   # haut   : garder la casquette
        int(w * 0.95),   # droite : couper le bord
        int(h * 0.90),   # bas    : couper épaules
    ))

    # ── Amélioration contraste et netteté ─────────────────────────────────
    crop = ImageEnhance.Contrast(crop).enhance(1.8)
    crop = ImageEnhance.Sharpness(crop).enhance(2.0)
    crop = ImageEnhance.Brightness(crop).enhance(1.1)
    crop = crop.convert("L")  # Niveaux de gris après amélioration couleur

    # Égalisation d'histogramme manuelle pour maximiser la plage de gris
    # → les détails du visage ressortent mieux
    from PIL import ImageOps
    crop = ImageOps.autocontrast(crop, cutoff=3)

    # Redimensionner — les chars ASCII sont ~2x plus hauts que larges
    # On compense en demandant rows*2 puis sous-échantillonnage vertical
    crop = crop.resize((cols, rows * 2), Image.LANCZOS)

    lines = []
    for row in range(rows):
        line = ""
        for col in range(cols):
            b = crop.getpixel((col, row * 2))
            line += brightness_to_char(b)
        lines.append(line)
    return lines

def main():
    print(f"Conversion de {IMG_PATH} (v2 — zoom visage)...")
    lines = image_to_ascii(IMG_PATH, COLS, ROWS)

    print("\n" + "=" * COLS)
    for line in lines:
        print(line)
    print("=" * COLS + "\n")

    escaped = [repr(line) for line in lines]
    content = f'''# Auto-généré par generate_ascii.py v2 — portrait de Jim
JIM_ASCII = [
{chr(10).join("    " + e + "," for e in escaped)}
]

JIM_LABEL = "*** BON ANNIVERSAIRE JIM ! ***"
'''
    with open(OUT_PATH, "w") as f:
        f.write(content)
    print(f"Généré : {OUT_PATH} ({COLS}x{len(lines)})")

if __name__ == "__main__":
    main()
