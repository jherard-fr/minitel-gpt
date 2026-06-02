#!/usr/bin/env python3
"""Service principal — boucle de conversation Claude (Anthropic) sur Minitel."""

import json
import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from minitel_serial import MinitelSerial

ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_COLS = 40  # Minitel : 40 colonnes mode standard
PROMPTS_FILE = Path(__file__).parent.parent / "config" / "prompts.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [minitel-chatgpt] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/minitel/minitel-gpt/logs/chatgpt.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

FALLBACK_PROMPT = (
    "Tu es un assistant IA affiche sur un terminal Minitel. "
    "Reponds de maniere concise (max 15 lignes de 40 caracteres). "
    "ASCII uniquement, sans accents."
)


def load_system_prompt() -> tuple[str, str]:
    """Charge le prompt actif depuis prompts.json. Retourne (label, system)."""
    try:
        with open(PROMPTS_FILE) as f:
            data = json.load(f)
        active_key = data.get("active", "")
        preset = data.get("presets", {}).get(active_key, {})
        return preset.get("label", active_key), preset.get("system", FALLBACK_PROMPT)
    except Exception as e:
        log.warning(f"Impossible de charger prompts.json : {e} — fallback utilisé")
        return "fallback", FALLBACK_PROMPT


def wrap_text(text: str, width: int = MAX_COLS) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            if len(current) + len(word) + (1 if current else 0) <= width:
                current = (current + " " + word).lstrip() if current else word
            else:
                if current:
                    lines.append(current)
                current = word[:width]
        if current:
            lines.append(current)
    return lines


def send_wrapped(m: MinitelSerial, text: str):
    for line in wrap_text(text):
        m.send_text(line + "\r\n")
        time.sleep(0.04)


def run():
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    m = MinitelSerial()
    m.open()

    history: list[dict] = []

    # Charger le prompt actif
    prompt_label, system_prompt = load_system_prompt()
    log.info(f"Prompt chargé : '{prompt_label}'")

    m.clear_screen()
    m.cursor_home()
    m.send_text("=" * MAX_COLS + "\r\n")
    m.send_text("   MINITEL GPT - powered by Claude\r\n")
    m.send_text("=" * MAX_COLS + "\r\n")
    m.send_text("Tapez votre question + ENTREE\r\n")
    m.send_text("SOMMAIRE = effacer l'ecran\r\n")
    m.send_text("-" * MAX_COLS + "\r\n")

    log.info(f"Boucle principale démarrée (modèle: {MODEL})")

    while True:
        m.send_text("> ")
        user_input = m.read_line(echo=True, timeout=300)

        if not user_input.strip():
            continue

        log.info(f"Entrée : {repr(user_input)}")

        if user_input.strip().upper() == "SOMMAIRE":
            m.clear_screen()
            m.cursor_home()
            continue

        history.append({"role": "user", "content": user_input})

        m.send_text("Connexion Claude...\r\n")
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=600,
                system=system_prompt,
                messages=history,
            )
            answer = response.content[0].text.strip()
            history.append({"role": "assistant", "content": answer})

            # Supprimer les accents pour le Minitel 7 bits
            answer_ascii = answer.encode("ascii", errors="replace").decode("ascii")

            m.send_text("-" * MAX_COLS + "\r\n")
            send_wrapped(m, answer_ascii)
            m.send_text("-" * MAX_COLS + "\r\n")
            log.info(f"Réponse envoyée ({len(answer)} chars)")

        except Exception as e:
            log.error(f"Erreur Claude : {e}")
            m.send_text(f"ERREUR: {str(e)[:60]}\r\n")

        # Garder l'historique court : système + 10 échanges max
        if len(history) > 20:
            history = history[-20:]


if __name__ == "__main__":
    run()
