# MINITEL GPT

Transformer un **Minitel** (testé sur **Minitel 1 Telic / Alcatel** et
**Minitel 2**) en terminal de chat IA autonome, piloté par un **Raspberry Pi
Zero 2 W**.

On tape sa question sur le clavier du Minitel, le Pi interroge un modèle
**Mistral** et affiche la réponse à l'écran, à 1200 bauds. La personnalité de
l'assistant est configurable via une interface web (la version phare est
« bloquée dans les années 80 »).

🌐 Présentation du projet : https://minitel-gpt.herard.com

---

## Matériel

| Élément | Détail |
|---|---|
| Raspberry Pi Zero 2 W | Raspberry Pi OS Lite (Bookworm) — ou **Pi Zero W v1** (voir ci-dessous) |
| Adaptateur USB-série | **FTDI FT232RL**, jumper sur **5 V** |
| Câble | OTG micro-USB (FTDI → port USB *data* du Pi) |
| Minitel | Prise DIN 5 broches « péri-informatique » — testé sur **Minitel 1** (Telic/Alcatel) et **Minitel 2** |

> **Compatible Pi Zero W (v1, 2017)** : en cas de pénurie de Zero 2 W, le Zero W
> d'origine fonctionne. Le LLM est appelé en HTTP (`requests`), sans dépendance
> lourde à compiler — l'installation passe donc sur l'architecture ARMv6.
> Flasher **Raspberry Pi OS Lite 32-bit**. Le CPU plus lent n'a quasi aucun impact :
> l'affichage est de toute façon limité par la liaison série à 1200 bauds.

### Câblage série

| FTDI | DIN Minitel | Rôle |
|---|---|---|
| TXD | broche 1 | Pi → Minitel (RX) |
| RXD | broche 3 | Minitel → Pi (TX) |
| GND | broche 2 | masse commune |

Paramètres série : **1200 bauds, 7 bits, parité paire, 1 stop (7E1)** — norme Videotex.
Le port apparaît côté Pi comme `/dev/ttyUSB0`.

> ⚠️ **Seules les broches 1, 2 et 3 servent.** Laisser les broches **4 et 5
> libres** (la broche 5 porte une **alimentation/tension**). Ne jamais ponter une
> broche de signal vers la 4 ou la 5 : sur un Minitel 2 cela bloque la réception.

> **Activation selon le modèle** (testé sur Minitel 1 **et** Minitel 2) :
>
> - **Minitel 1** (Telic / Alcatel) : le port DIN affiche les données **par
>   défaut**, aucune manipulation — le service est prêt dès l'allumage.
> - **Minitel 2** : démarre sur son **Répertoire** local. À chaque allumage :
>   appuyer sur **`Fnct + Sommaire`** (quitte le Répertoire, connecte la prise à
>   l'écran en Vidéotex), puis sur **`Sommaire`** pour afficher l'accueil
>   MINITEL GPT.
>   ⚠️ **Ne pas** faire `Fnct + T` puis `A` : cela bascule en mode
>   *téléinformatique* (80 colonnes défilant, sans pagination) au lieu du beau
>   Vidéotex 40 colonnes.
>
> **Compatibilité entre modèles** : le brochage DIN est *normalisé*
> (norme Télétel/STUM), identique sur tous les Minitels à prise péri-informatique.
> Le service reconnaît les touches de fonction en Vidéotex (`SEP`) **et** en
> téléinformatique (VT100 `ESC O x`), et re-force le Vidéotex au besoin.

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

Le script `install.sh` se charge de **tout** : paquets (`pyserial`, `flask`,
`python-dotenv`, `requests`, `pyfiglet`, `dnsmasq-base`, `iw`), désactivation du
`dnsmasq` système (conflit hotspot), groupe `dialout`, règle sudo, et activation
des 3 services systemd.

### Fichier `.env`

```env
MISTRAL_KEY=...
MISTRAL_MODEL=mistral-small-latest
```

> La clé Mistral peut aussi être saisie depuis l'interface d'admin
> (onglet **Paramètres**). Crée-la sur https://console.mistral.ai/

### Préparation de la carte SD (avant tout)

Avec **Raspberry Pi Imager** : flasher **Raspberry Pi OS Lite (64-bit)**, et dans
les réglages (⚙) : activer **SSH**, définir l'utilisateur **`minitel`** + mot de
passe, et renseigner le **WiFi** initial. Le projet est entièrement *headless*
(ni écran ni clavier sur le Pi).

### Mettre à jour le code (après installation)

```bash
cd /home/minitel/minitel-gpt
git pull
sudo systemctl restart minitel-chatgpt admin-ui wifi-manager
```

---

## Services systemd

| Service | Rôle |
|---|---|
| `minitel-chatgpt` | Terminal : lit le clavier Minitel, interroge Mistral, affiche la réponse paginée |
| `wifi-manager` | Connexion WiFi autonome + hotspot de provisioning (portail captif) |
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

`http://<ip-du-pi>:8080` — mot de passe par défaut **mistral** (`ADMIN_PASSWORD`).

Trois onglets :
- **Tableau de bord** : état des services, activation des personnalités
- **Personnalités** : créer / modifier / supprimer des presets, génération de
  prompt par IA, **fichiers de connaissance** (.txt) injectés dans le contexte,
  textes d'accueil personnalisables
- **Paramètres** : clé API Mistral, logs

Les personnalités sont stockées dans `config/prompts.json`, leurs fichiers de
connaissance dans `config/knowledge/<personnalité>/`.

L'adresse de l'admin est aussi consultable **sur le Minitel via la touche Guide**.

---

## WiFi autonome

- Au démarrage, le Pi rejoint un réseau connu.
- Sans réseau connu pendant ~2 min, il bascule en **hotspot ouvert
  `MinitelGPT-Setup`** (IP `192.168.4.1`).
- Se connecter au hotspot ouvre automatiquement le **portail captif** :
  on choisit le réseau du lieu, le Pi s'y connecte et coupe le hotspot.
- L'IP du Pi est ensuite consultable sur le Minitel (touche **Guide**).

---

## Arborescence

```
services/
  minitel_chatgpt.py   terminal (boucle de chat, appel Mistral)
  minitel_serial.py    abstraction série
  wifi_manager.py      provisioning WiFi + portail captif
  admin_ui.py          interface web d'admin
config/
  prompts.json         personnalités
  knowledge/           fichiers .txt par personnalité
  *.service            unités systemd
  minitel-gpt-sudoers  règle sudo pour l'admin
install.sh             installation
```

---

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Rien ne s'affiche sur le Minitel | fil série délogé (cause n°1), jumper FTDI pas sur 5 V, broche 4/5 pontée par erreur, ou Minitel 2 resté dans le Répertoire (faire `Fnct + Sommaire`) |
| Minitel 2 : écran d'accueil vide après `Fnct + Sommaire` | normal — appuyer sur `Sommaire` pour afficher MINITEL GPT |
| Affichage 80 colonnes qui défile sans pagination | Minitel 2 passé en mode téléinformatique via `Fnct + T A` — éviter cette combinaison (rester en `Fnct + Sommaire`) |
| Charabia à l'écran | vitesse Pi ≠ vitesse Minitel (rester à 1200 bauds des deux côtés) |
| Le hotspot n'apparaît pas | service `dnsmasq` système actif (port 53) → le désactiver |
| Caractères doublés à la saisie | écho local du Minitel + écho logiciel (ne pas ré-écho côté Pi) |
| Touches de fonction sans effet | Minitel 2 en mode téléinfo (touches VT100, gérées) ou octet `0x13` isolé (corrigé) |

---

*Projet personnel de Jérôme Hérard.*
