# MINITEL GPT

Transformer un **Minitel 1 Telic / Alcatel** en terminal de chat IA autonome,
piloté par un **Raspberry Pi Zero 2 W**.

On tape sa question sur le clavier du Minitel, le Pi interroge un modèle Claude
(Anthropic) et affiche la réponse à l'écran, à 1200 bauds. La personnalité de
l'assistant est configurable via une interface web (la version phare est
« bloquée dans les années 80 »).

🌐 Présentation du projet : https://minitel-gpt.herard.com

---

## Matériel

| Élément | Détail |
|---|---|
| Raspberry Pi Zero 2 W | Raspberry Pi OS Lite (Bookworm) |
| Adaptateur USB-série | **FTDI FT232RL**, jumper sur **5 V** |
| Câble | OTG micro-USB (FTDI → port USB *data* du Pi) |
| Minitel | Telic / Alcatel 1, prise DIN 5 broches « péri-informatique » |

### Câblage série

| FTDI | DIN Minitel | Rôle |
|---|---|---|
| TXD | broche 1 | Pi → Minitel (RX) |
| RXD | broche 3 | Minitel → Pi (TX) |
| GND | broche 2 | masse commune |

Paramètres série : **1200 bauds, 7 bits, parité paire, 1 stop (7E1)** — norme Videotex.
Le port apparaît côté Pi comme `/dev/ttyUSB0`.

> **Activation du Minitel** : pour qu'il reçoive/affiche les données série, le
> mettre en mode péri-informatique avec **Fnct + T** puis **A**.

---

## Installation

```bash
# 1. Cloner le projet dans le home de l'utilisateur 'minitel'
cd /home/minitel
git clone https://github.com/jherard-fr/minitel-gpt.git
cd minitel-gpt

# 2. Créer le fichier .env (voir section ci-dessous)
cp config/env.example .env
nano .env

# 3. Lancer l'installation (dépendances + services systemd)
sudo bash install.sh
```

Le script `install.sh` installe les dépendances (`pyserial`, `flask`,
`python-dotenv`, `requests`, `anthropic`, `pyfiglet`, `dnsmasq-base`, `iw`),
ajoute l'utilisateur au groupe `dialout`, et active les services systemd.

### Fichier `.env`

```env
ANTHROPIC_KEY=sk-ant-...
CLAUDE_MODEL=claude-haiku-4-5-20251001
RESEND_API_KEY=re_...
MAIL_TO=vous@exemple.com
```

> La clé Anthropic et l'email peuvent aussi être saisis depuis l'interface d'admin.

### Réglages système requis

```bash
# UART PL011 stable (si usage GPIO au lieu du FTDI) : /boot/firmware/config.txt
#   enable_uart=1
#   dtoverlay=disable-bt

# Hotspot WiFi : désactiver le dnsmasq système (conflit port 53 avec NetworkManager)
sudo systemctl disable --now dnsmasq

# Autoriser l'admin web à redémarrer le terminal sans mot de passe
sudo cp config/minitel-gpt-sudoers /etc/sudoers.d/minitel-gpt
sudo chmod 440 /etc/sudoers.d/minitel-gpt
```

---

## Services systemd

| Service | Rôle |
|---|---|
| `minitel-chatgpt` | Terminal : lit le clavier Minitel, interroge Claude, affiche la réponse paginée |
| `wifi-manager` | Connexion WiFi autonome + hotspot de provisioning (portail captif) |
| `boot-notify` | Envoie l'IP du Pi par email au démarrage et après config WiFi |
| `admin-ui` | Interface web d'administration (port 8080) |

```bash
sudo systemctl status minitel-chatgpt     # état
sudo systemctl restart minitel-chatgpt    # redémarrer
tail -f logs/chatgpt.log                  # logs
```

> ⚠️ Ne pas lancer le script du terminal à la main en parallèle du service :
> deux instances se disputeraient le port série. Toujours
> `sudo pkill -9 -f minitel_chatgpt` avant un lancement manuel de debug.

---

## Interface d'administration

`http://<ip-du-pi>:8080` — mot de passe par défaut **13100** (`ADMIN_PASSWORD`).

Trois onglets :
- **Tableau de bord** : état des services, activation des personnalités
- **Personnalités** : créer / modifier / supprimer des presets, génération de
  prompt par IA, textes d'accueil personnalisables
- **Paramètres** : clé Anthropic, email de notification, logs

Les personnalités sont stockées dans `config/prompts.json`.

---

## WiFi autonome

- Au démarrage, le Pi rejoint un réseau connu.
- Sans réseau connu pendant ~2 min, il bascule en **hotspot ouvert
  `MinitelGPT-Setup`** (IP `192.168.4.1`).
- Se connecter au hotspot ouvre automatiquement le **portail captif** :
  on choisit le réseau du lieu, le Pi s'y connecte et coupe le hotspot.
- L'IP finale est envoyée par email (Resend).

---

## Arborescence

```
services/
  minitel_chatgpt.py   terminal (boucle de chat)
  minitel_serial.py    abstraction série
  wifi_manager.py      provisioning WiFi + portail
  admin_ui.py          interface web d'admin
  boot_notify.py       email d'IP au boot
config/
  prompts.json         personnalités
  *.service            unités systemd
  minitel-gpt-sudoers  règle sudo pour l'admin
install.sh             installation
```

---

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Rien ne s'affiche sur le Minitel | fil série délogé, ou Minitel pas en mode péri-info (Fnct+T A) |
| Le hotspot n'apparaît pas | service `dnsmasq` système actif (port 53) → le désactiver |
| Caractères doublés à la saisie | écho local du Minitel + écho logiciel (ne pas ré-écho côté Pi) |
| Touches de fonction sans effet | un octet `0x13` isolé bloquait la lecture (corrigé) |

---

*Projet personnel de Jérôme Hérard.*
