#!/usr/bin/env python3
"""Notification email au boot — envoie l'IP locale via Resend."""

import os
import sys
import time
import socket
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

RESEND_API_KEY = os.environ["RESEND_API_KEY"]
MAIL_TO = os.environ["MAIL_TO"]
# Utiliser un domaine vérifié dans ton compte Resend (resend.com/domains)
# En attendant : onboarding@resend.dev fonctionne pour envoyer à jerome@herard.com
FROM_EMAIL = os.getenv("RESEND_FROM", "onboarding@resend.dev")
HOSTNAME = socket.gethostname()


def get_ip(iface: str = "wlan0") -> str | None:
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", iface], text=True
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
    except Exception:
        pass
    return None


def wait_for_ip(timeout: int = 60) -> str | None:
    """Attend l'IP DHCP, max timeout secondes."""
    start = time.time()
    while time.time() - start < timeout:
        ip = get_ip("wlan0") or get_ip("usb0")
        if ip:
            return ip
        time.sleep(3)
    return None


def send_email(ip: str):
    admin_url = f"http://{ip}:8080"
    body_text = f"{HOSTNAME} est disponible\n\nAdmin : {admin_url}\nSSH   : ssh minitel@{ip}\n"
    body_html = f"""<h2>{HOSTNAME} est disponible</h2>
<p><b>Admin :</b> <a href="{admin_url}">{admin_url}</a> (mot de passe : 13100)</p>
<p><b>SSH   :</b> <code>ssh minitel@{ip}</code></p>"""

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "minitel-gpt/1.0",
        },
        json={
            "from": FROM_EMAIL,
            "to": [MAIL_TO],
            "subject": f"[{HOSTNAME}] disponible sur {ip}",
            "text": body_text,
            "html": body_html,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    print(f"[boot-notify] Attente IP...")
    ip = wait_for_ip(timeout=60)
    if not ip:
        print("[boot-notify] Pas d'IP après 60s — abandon")
        sys.exit(1)

    print(f"[boot-notify] IP obtenue : {ip}")
    try:
        result = send_email(ip)
        print(f"[boot-notify] Email envoyé : {result}")
    except Exception as e:
        print(f"[boot-notify] Erreur envoi email : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
