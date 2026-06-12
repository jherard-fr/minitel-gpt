#!/usr/bin/env python3
"""
WiFi Manager — provisioning WiFi style IoT (Sonos/Chromecast).

Comportement :
  1. Au boot : tente de rejoindre un réseau connu (30s timeout)
  2. Si échec : crée le hotspot MinitelGPT-Setup sur 192.168.4.1
  3. Expose une page Web pour scanner et configurer un nouveau réseau
  4. En cas de succès WiFi : coupe le hotspot, relance les services
"""

import os
import sys
import time
import subprocess
import threading
import logging
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, redirect

AP_SSID = "MinitelGPT-Setup"
AP_PASSWORD = "minitelgpt"  # WPA2, min 8 chars
AP_IP = "192.168.4.1"
AP_CON_NAME = "MinitelGPT-AP"
CONNECT_TIMEOUT = 30  # secondes pour rejoindre un réseau connu
FLASK_PORT = 80

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [wifi-manager] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/minitel/minitel-gpt/logs/wifi.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

app = Flask(__name__)


# ── Portail captif ──────────────────────────────────────────────────────────
# Quand le hotspot est actif, on redirige toute requête (et les sondes de
# détection des OS) vers le portail, pour qu'il s'ouvre automatiquement.
CAPTIVE_PROBES = (
    "/generate_204", "/gen_204", "/ncsi.txt", "/connecttest.txt",
    "/hotspot-detect.html", "/library/test/success.html",
    "/canonical.html", "/success.txt", "/redirect",
)

@app.before_request
def captive_redirect():
    from flask import request, redirect as _redir
    host = request.host.split(":")[0]
    path = request.path
    # Si on est en hotspot et que la requête ne vise pas déjà notre IP,
    # ou que c'est une sonde de détection captive → renvoyer vers le portail.
    if host != AP_IP and path != "/connect":
        try:
            if hotspot_active():
                return _redir(f"http://{AP_IP}/", code=302)
        except Exception:
            pass
    if path in CAPTIVE_PROBES:
        return _redir(f"http://{AP_IP}/", code=302)


# ── Utilitaires nmcli ──────────────────────────────────────────────────────

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    log.debug(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def is_connected() -> str | None:
    """Retourne l'IP wlan0 si connecté, None sinon."""
    try:
        out = run(["ip", "-4", "addr", "show", "wlan0"]).stdout
        for line in out.splitlines():
            if "inet " in line:
                return line.strip().split()[1].split("/")[0]
    except Exception:
        pass
    return None


def hotspot_active() -> bool:
    r = run(["nmcli", "-t", "-f", "NAME,STATE", "con", "show", "--active"], check=False)
    return AP_CON_NAME in r.stdout


def client_connected() -> str | None:
    """
    Retourne le nom du réseau CLIENT actif sur wlan0 (hors hotspot), ou None.
    Distingue une vraie connexion WiFi d'un hotspot : en mode AP, wlan0 a aussi
    une IP (192.168.4.1) mais ce n'est PAS une connexion client.
    """
    r = run(["nmcli", "-t", "-f", "NAME,DEVICE", "con", "show", "--active"], check=False)
    for line in r.stdout.splitlines():
        p = line.split(":")
        if len(p) >= 2 and p[1] == "wlan0" and p[0] != AP_CON_NAME:
            return p[0]
    return None


def scan_networks() -> list[dict]:
    run(["nmcli", "dev", "wifi", "rescan"], check=False)
    time.sleep(2)
    r = run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list"], check=False)
    networks = []
    seen = set()
    for line in r.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        ssid = parts[0].strip()
        if not ssid or ssid == AP_SSID or ssid in seen:
            continue
        seen.add(ssid)
        networks.append({
            "ssid": ssid,
            "signal": int(parts[1]) if parts[1].isdigit() else 0,
            "security": parts[2] or "Open",
            "connected": parts[3] == "*",
        })
    return sorted(networks, key=lambda n: -n["signal"])


def client_wifi_connections():
    """Liste les noms des profils WiFi client (hors hotspot)."""
    r = run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"], check=False)
    names = []
    for line in r.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and "wireless" in parts[1] and parts[0] != AP_CON_NAME:
            names.append(parts[0])
    return names


def set_clients_autoconnect(enabled: bool):
    """Active/désactive l'autoconnect de tous les réseaux clients."""
    val = "yes" if enabled else "no"
    for name in client_wifi_connections():
        run(["nmcli", "con", "modify", name, "connection.autoconnect", val], check=False)


def create_hotspot():
    log.info(f"Création hotspot {AP_SSID}")
    # 1. Empêcher NetworkManager de reprendre wlan0 avec un réseau connu :
    #    désactiver l'autoconnect des clients et les déconnecter.
    set_clients_autoconnect(False)
    for name in client_wifi_connections():
        run(["nmcli", "con", "down", name], check=False)
    time.sleep(1)

    # 2. (Re)créer le profil AP — réseau OUVERT (sans mot de passe) pour
    #    faciliter la connexion au portail de configuration.
    run(["nmcli", "con", "delete", AP_CON_NAME], check=False)
    run([
        "nmcli", "con", "add",
        "type", "wifi",
        "ifname", "wlan0",
        "mode", "ap",
        "con-name", AP_CON_NAME,
        "ssid", AP_SSID,
        "802-11-wireless.band", "bg",
        "802-11-wireless.channel", "6",
        "ipv4.method", "shared",
        "ipv4.addresses", f"{AP_IP}/24",
        "ipv6.method", "disabled",
        "autoconnect", "no",
    ], check=True)
    run(["nmcli", "con", "up", AP_CON_NAME], check=True)
    log.info(f"Hotspot OUVERT actif sur {AP_IP}")


def stop_hotspot():
    log.info("Arrêt hotspot")
    run(["nmcli", "con", "down", AP_CON_NAME], check=False)
    # Réactiver l'autoconnect des clients pour qu'ils se reconnectent
    set_clients_autoconnect(True)


def connect_wifi(ssid: str, password: str) -> tuple[bool, str]:
    """Tente de connecter à un réseau. Retourne (succès, ip_ou_erreur)."""
    log.info(f"Connexion WiFi → {ssid}")
    stop_hotspot()
    time.sleep(1)

    # Supprimer TOUS les profils existants ayant ce SSID (recherche par SSID,
    # pas par nom : un profil 'Verrieres' peut porter le SSID 'Freebox-XXX').
    r = run(["nmcli", "-t", "-f", "NAME", "con", "show"], check=False)
    for name in r.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        s = run(["nmcli", "-t", "-f", "802-11-wireless.ssid", "con", "show", name],
                check=False)
        if f":{ssid}" in s.stdout.strip():
            log.info(f"Suppression du profil existant '{name}' (SSID {ssid})")
            run(["nmcli", "con", "delete", name], check=False)

    # Créer le profil explicitement avec le bon type de sécurité
    add_cmd = ["nmcli", "con", "add", "type", "wifi", "ifname", "wlan0",
               "con-name", ssid, "ssid", ssid,
               "ipv4.method", "auto", "autoconnect", "yes"]
    if password:
        add_cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    run(add_cmd, check=False)

    result = run(["nmcli", "con", "up", ssid], check=False)
    if result.returncode != 0:
        log.error(f"nmcli connect échoué : {result.stderr.strip()}")
        run(["nmcli", "con", "delete", ssid], check=False)  # nettoyer le profil raté
        create_hotspot()
        return False, result.stderr.strip()

    # Attendre l'IP
    for _ in range(15):
        ip = is_connected()
        if ip:
            log.info(f"Connecté à {ssid} — IP {ip}")
            return True, ip
        time.sleep(2)

    create_hotspot()
    return False, "Timeout — pas d'IP obtenue"


def try_known_networks(timeout: int = CONNECT_TIMEOUT) -> bool:
    log.info("Recherche réseaux connus...")
    start = time.time()
    while time.time() - start < timeout:
        if is_connected():
            log.info(f"Déjà connecté : {is_connected()}")
            return True
        time.sleep(3)
    return False


# ── Interface Web ──────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>MinitelGPT — Configuration WiFi</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px;
    max-width: 600px; margin: 0 auto; }
  h1 { color: #00ff88; font-size: 1.3em; }
  .card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 16px; margin: 12px 0; }
  .network { cursor: pointer; padding: 10px; border-radius: 4px; margin: 4px 0; border: 1px solid #0f3460; }
  .network:hover { background: #0f3460; }
  .network.selected { border-color: #00ff88; }
  .signal { float: right; color: #888; }
  .security { font-size: 0.8em; color: #aaa; }
  input[type=password] { width: 100%; padding: 10px; background: #0f3460; border: 1px solid #00ff88;
    color: #e0e0e0; border-radius: 4px; box-sizing: border-box; margin-top: 8px; font-family: monospace;
    font-size: 16px; }
  button { background: #00ff88; color: #1a1a2e; border: none; padding: 10px 24px;
    border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 10px; font-size: 1em; }
  button:hover { background: #00cc66; }
  .status { padding: 10px; border-radius: 4px; margin: 8px 0; }
  .ok { background: #0d3320; color: #00ff88; border: 1px solid #00ff88; }
  .err { background: #330d0d; color: #ff4444; border: 1px solid #ff4444; }
  #spinner { display: none; color: #aaa; margin-top: 8px; }
</style>
</head>
<body>
<h1>🖥 MinitelGPT — Configuration WiFi</h1>

{% if status_msg %}
<div class="status {{ 'ok' if status_ok else 'err' }}">{{ status_msg }}</div>
{% endif %}

<div class="card">
<b>Réseaux disponibles</b> — <a href="/" style="color:#888;font-size:0.85em">Rafraîchir</a>
<div id="networks">
{% for net in networks %}
<div class="network" onclick="selectNet('{{ net.ssid }}')" id="net-{{ loop.index }}">
  {{ net.ssid }}
  <span class="signal">📶 {{ net.signal }}%</span><br>
  <span class="security">{{ net.security }}</span>
  {% if net.connected %}<span style="color:#00ff88"> ✓ connecté</span>{% endif %}
</div>
{% endfor %}
{% if not networks %}<p style="color:#888">Aucun réseau détecté</p>{% endif %}
</div>
</div>

<div class="card">
<form id="wifiForm" onsubmit="connectWifi(event)">
  <b>Réseau sélectionné :</b> <span id="selectedSSID" style="color:#00ff88">—</span>
  <input type="hidden" id="ssid" name="ssid">
  <input type="password" id="password" name="password" placeholder="Mot de passe WiFi" autocomplete="off">
  <br>
  <button type="submit">Se connecter</button>
  <div id="spinner">⏳ Connexion en cours (30s max)...</div>
</form>
</div>

<script>
function selectNet(ssid) {
  document.getElementById('selectedSSID').textContent = ssid;
  document.getElementById('ssid').value = ssid;
  document.querySelectorAll('.network').forEach(el => el.classList.remove('selected'));
  event.currentTarget.classList.add('selected');
  document.getElementById('password').focus();
}
async function connectWifi(e) {
  e.preventDefault();
  const ssid = document.getElementById('ssid').value;
  if (!ssid) { alert('Sélectionnez un réseau'); return; }
  document.getElementById('spinner').style.display = 'block';
  // On envoie la demande SANS attendre la fin (le hotspot va se couper).
  fetch('/connect', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ssid, password: document.getElementById('password').value})
  }).catch(()=>{});
  // Confirmation immédiate, affichée AVANT que le hotspot se ferme.
  document.body.innerHTML = '<div style="padding:40px;color:#00ff88;font-family:monospace;text-align:center">'
    + '<h2>&#10003; Configuration enregistree !</h2>'
    + '<p>Le Minitel se connecte a <b>' + ssid + '</b>.</p>'
    + '<p>Ce reseau de configuration va se fermer dans quelques secondes.<br>'
    + 'Reconnectez votre telephone a votre WiFi habituel.</p>'
    + '<p style="color:#aaa;margin-top:20px">Vous recevrez un email avec la nouvelle adresse du Minitel.</p></div>';
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    networks = scan_networks()
    return render_template_string(HTML, networks=networks, status_msg=None, status_ok=False)


@app.route("/connect", methods=["POST"])
def connect():
    data = request.json or {}
    ssid = data.get("ssid", "").strip()
    password = data.get("password", "").strip()

    if not ssid:
        return jsonify(success=False, error="SSID manquant")

    def do_connect():
        # Laisser le temps à la page de confirmation de s'afficher avant de
        # couper le hotspot (sinon le client perd la connexion avant de la voir).
        time.sleep(3)
        success, result = connect_wifi(ssid, password)
        if success:
            subprocess.run(["systemctl", "start", "minitel-chatgpt"], check=False)
            subprocess.run(["systemctl", "start", "boot-notify"], check=False)
        else:
            log.warning(f"Connexion à {ssid} échouée : {result}")

    threading.Thread(target=do_connect, daemon=True).start()
    # Réponse immédiate : la confirmation s'affiche tout de suite, AVANT la bascule.
    return jsonify(success=True, ssid=ssid)


@app.route("/status")
def status():
    ip = is_connected()
    return jsonify(connected=bool(ip), ip=ip, hotspot=hotspot_active())


# ── Surveillance continue ──────────────────────────────────────────────────
CHECK_INTERVAL = 30        # secondes entre deux vérifications
GRACE_CYCLES = 4           # cycles déconnectés avant hotspot (~2 min)


def monitor_loop():
    """
    Surveille la connexion en permanence.
    - Connecté : s'assure que le hotspot est coupé.
    - Déconnecté plus de GRACE_CYCLES cycles : bascule en hotspot de provisioning.
    Le portail web (Flask) tourne en permanence en parallèle (port 80),
    accessible aussi bien via le WiFi que via le hotspot.
    """
    log.info("=== WiFi Manager (surveillance continue) démarré ===")
    disconnected = 0
    while True:
        client = client_connected()   # réseau CLIENT réel (pas le hotspot)
        if client:
            # Connecté à un vrai réseau WiFi
            if disconnected or hotspot_active():
                log.info(f"Connecté à '{client}' → arrêt du hotspot si actif")
            disconnected = 0
            if hotspot_active():
                stop_hotspot()
        elif hotspot_active():
            # En mode hotspot : on y reste (attente config via le portail)
            disconnected = 0
        else:
            # Ni client, ni hotspot → on compte avant de basculer
            disconnected += 1
            log.info(f"Déconnecté ({disconnected}/{GRACE_CYCLES})")
            if disconnected >= GRACE_CYCLES:
                log.info("Aucun réseau → bascule en hotspot MinitelGPT-Setup")
                try:
                    create_hotspot()
                    log.info(f"Hotspot actif — portail http://{AP_IP}")
                except Exception as e:
                    log.error(f"Échec création hotspot : {e}")
        time.sleep(CHECK_INTERVAL)


def main():
    # Portail web en permanence (thread daemon) : configuration WiFi accessible
    # depuis le hotspot (192.168.4.1) ou depuis le réseau local.
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=FLASK_PORT,
                               debug=False, use_reloader=False),
        daemon=True,
    ).start()
    monitor_loop()


if __name__ == "__main__":
    main()
