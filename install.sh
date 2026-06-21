#!/bin/bash
# install.sh - Installation complète de MINITEL GPT sur Raspberry Pi
# Prérequis : avoir cloné le dépôt dans /home/minitel/minitel-gpt
#   cd /home/minitel && git clone https://github.com/jherard-fr/minitel-gpt.git
# Usage : sudo bash install.sh
set -e

PROJ_DIR="/home/minitel/minitel-gpt"
SERVICE_DIR="/etc/systemd/system"

echo "=== MINITEL GPT - Installation ==="

# ── Dépendances système ─────────────────────────────────────────────────────
echo "[1/7] Paquets système..."
apt-get update -q
apt-get install -y \
  git \
  python3-serial python3-requests python3-flask python3-dotenv \
  dnsmasq-base iw minicom
#   git         : mise à jour de l'app depuis l'admin web (git fetch/reset)
#   python3-*   : pyserial (port Minitel), requests (Mistral), flask + dotenv (admin)
#   dnsmasq-base + iw : hotspot WiFi de provisioning
#   minicom     : utilitaire de debug série (optionnel)

# ── Dépendances Python (hors apt) ───────────────────────────────────────────
echo "[2/7] Paquets Python..."
python3 -m pip install pyfiglet --break-system-packages   # titre ASCII de l'accueil

# ── Désactiver le dnsmasq système (conflit port 53 avec le hotspot) ─────────
echo "[3/7] Nettoyage dnsmasq système..."
systemctl disable --now dnsmasq 2>/dev/null || true
# NetworkManager utilise son propre dnsmasq-base interne pour le hotspot.

# ── Permissions port série + répertoires ────────────────────────────────────
echo "[4/7] Permissions et répertoires..."
usermod -a -G dialout minitel                 # accès à /dev/ttyUSB0 (FTDI)
mkdir -p "$PROJ_DIR/logs" "$PROJ_DIR/config/knowledge"
chown -R minitel:minitel "$PROJ_DIR"

# ── Personnalités : prompts.json est local (gitignoré) ──────────────────────
echo "[5/7] Initialisation des personnalités..."
# prompts.json (édité via l'admin) n'est pas versionné, pour qu'une mise à jour
# ne l'écrase jamais. On le crée depuis le défaut fourni par le dépôt s'il manque.
if [ ! -f "$PROJ_DIR/config/prompts.json" ] && [ -f "$PROJ_DIR/config/prompts.default.json" ]; then
  cp "$PROJ_DIR/config/prompts.default.json" "$PROJ_DIR/config/prompts.json"
  chown minitel:minitel "$PROJ_DIR/config/prompts.json"
  echo "      prompts.json créé depuis prompts.default.json"
fi

# ── Règle sudo (l'admin web redémarre les services sans mot de passe) ───────
echo "[6/7] Règle sudo..."
cp "$PROJ_DIR/config/minitel-gpt-sudoers" /etc/sudoers.d/minitel-gpt
chmod 440 /etc/sudoers.d/minitel-gpt
visudo -c -f /etc/sudoers.d/minitel-gpt        # autorise systemctl restart des 3 services

# ── Services systemd ────────────────────────────────────────────────────────
echo "[7/7] Services systemd..."
cp "$PROJ_DIR/config/minitel-chatgpt.service" "$SERVICE_DIR/"
cp "$PROJ_DIR/config/wifi-manager.service"    "$SERVICE_DIR/"
cp "$PROJ_DIR/config/admin-ui.service"        "$SERVICE_DIR/"
systemctl daemon-reload
systemctl enable minitel-chatgpt.service wifi-manager.service admin-ui.service

echo ""
echo "=== Installation terminée ==="
echo ""
echo "1. Créer le fichier .env avec la clé Mistral :"
echo "     cp $PROJ_DIR/config/env.example $PROJ_DIR/.env"
echo "     nano $PROJ_DIR/.env      # renseigner MISTRAL_KEY"
echo ""
echo "2. Démarrer les services :"
echo "     sudo systemctl start minitel-chatgpt wifi-manager admin-ui"
echo ""
echo "3. Admin web : http://<ip-du-pi>:8080   (mot de passe : mistral)"
echo "   - onglet Parametres > Mise a jour : met a jour le code depuis GitHub"
echo "   - l'IP s'affiche aussi sur le Minitel via la touche GUIDE"
echo ""
echo "Cablage DIN : seules 3 broches (1=Rx, 2=GND, 3=Tx) ; 4 et 5 LIBRES."
echo "A l'allumage du Minitel :"
echo "  - Minitel 1 : rien a faire, l'accueil s'affiche."
echo "  - Minitel 2 : Fnct+Sommaire (sort du Repertoire) puis Sommaire."
echo "    NE PAS faire Fnct+T A (force le mode teleinformatique, defilant)."
echo "Si rien ne s'affiche : verifier contacts + jumper FTDI sur 5V."
