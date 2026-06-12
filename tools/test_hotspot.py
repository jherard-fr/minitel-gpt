#!/usr/bin/env python3
"""Diagnostic hotspot : crée, capture l'état système réel, restaure."""
import sys, time, subprocess
sys.path.insert(0, "/home/minitel/minitel-gpt/services")
from wifi_manager import create_hotspot, stop_hotspot

LOG = "/home/minitel/minitel-gpt/logs/hotspot_test.log"
def log(m):
    with open(LOG, "a") as f:
        f.write(f"{m}\n")
def cap(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(f"$ {cmd}\n{r.stdout}{r.stderr}")

KNOWN = "Verrieres"
try:
    log("=== CREATION HOTSPOT ===")
    create_hotspot()
    time.sleep(6)
    log("=== ETAT APRES CREATION ===")
    cap("nmcli -t -f NAME,DEVICE,STATE con show --active")
    cap("nmcli -f GENERAL.STATE,GENERAL.CONNECTION dev show wlan0")
    cap("iw dev")
    cap("rfkill list")
    cap("nmcli con show MinitelGPT-AP | grep -iE '802-11-wireless|ipv4.method|GENERAL.STATE'")
    cap("journalctl -u NetworkManager --no-pager -n 25")
    time.sleep(40)
except Exception as e:
    log(f"ERREUR: {e}")
finally:
    log("=== RESTAURATION ===")
    stop_hotspot(); time.sleep(2)
    for i in range(5):
        r = subprocess.run(["nmcli","con","up",KNOWN], capture_output=True, text=True)
        log(f"up {KNOWN} essai {i+1}: rc={r.returncode} {r.stderr.strip()}")
        if r.returncode == 0: break
        time.sleep(5)
    log("=== FIN ===")
