# MINITEL GPT

Transformer un **Minitel** (testé sur **Minitel 1 Telic / Alcatel** et
**Minitel 2**) en terminal de chat IA autonome, piloté par un **Raspberry Pi
Zero 2 W**.

On tape sa question sur le clavier du Minitel, le Pi interroge le modèle d'IA
choisi - **Mistral** ou **Claude** - et affiche la réponse à l'écran, à 1200
bauds. Le fournisseur, la clé et le modèle se règlent depuis l'interface web,
tout comme la personnalité de l'assistant (la version phare est « bloquée dans
les années 80 »).

🌐 Présentation du projet : https://minitel-gpt.herard.com

---

## Matériel

| Élément | Détail |
|---|---|
| Raspberry Pi | **Zero W**, **Zero 2 W** ou **Pi 3** (tous validés) - Raspberry Pi OS Lite. Le Zero W suffit (voir ci-dessous) |
| Adaptateur USB-série | **FTDI FT232RL**, jumper sur **5 V** |
| Câble | OTG micro-USB (FTDI → port USB *data* du Pi) |
| Minitel | Prise DIN 5 broches « péri-informatique » - testé sur **Minitel 1** (Telic/Alcatel) et **Minitel 2** |

> **Compatible Pi Zero W (v1, 2017), Zero 2 W et Pi 3** : les trois sont validés.
> En cas de pénurie de Zero 2 W, le Zero W d'origine fonctionne. Le LLM est appelé en HTTP (`requests`), sans dépendance
> lourde à compiler - l'installation passe donc sur l'architecture ARMv6.
> Flasher **Raspberry Pi OS Lite 32-bit**. Le CPU plus lent n'a quasi aucun impact :
> l'affichage est de toute façon limité par la liaison série à 1200 bauds.

### Câblage série

| FTDI | DIN Minitel | Rôle |
|---|---|---|
| TXD | broche 1 | Pi → Minitel (RX) |
| RXD | broche 3 | Minitel → Pi (TX) |
| GND | broche 2 | masse commune |

Paramètres série : **1200 bauds, 7 bits, parité paire, 1 stop (7E1)** - norme Videotex.
Le port apparaît côté Pi comme `/dev/ttyUSB0`.

> ⚠️ **Seules les broches 1, 2 et 3 servent.** Laisser les broches **4 et 5
> libres** (la broche 5 porte une **alimentation/tension**). Ne jamais ponter une
> broche de signal vers la 4 ou la 5 : sur un Minitel 2 cela bloque la réception.

> **Activation selon le modèle** (testé sur Minitel 1 **et** Minitel 2) :
>
> - **Minitel 1** (Telic / Alcatel) : le port DIN affiche les données **par
>   défaut**, aucune manipulation - le service est prêt dès l'allumage.
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
> Le service reconnaît les touches de fonction aussi bien en Vidéotex (`SEP`)
> qu'en téléinformatique (VT100 `ESC O x`), donc il fonctionne quel que soit le mode.

---

## Installation

### 1. Préparer la carte SD (avant tout)

Avec **Raspberry Pi Imager** (<https://www.raspberrypi.com/software/>) : flasher
**Raspberry Pi OS Lite**.

- **Pi Zero 2 W / Pi 3** : version **64-bit**.
- **Pi Zero W (v1)** : version **32-bit** - c'est la seule proposée par l'imageur
  pour ce modèle (CPU ARMv6, pas de 64-bit), c'est normal.

Dans les réglages (⚙) de l'imageur : activer **SSH**, définir l'utilisateur
**`minitel`** + un mot de passe, et renseigner le **WiFi** initial. Le projet est
entièrement *headless* : ni écran ni clavier branchés sur le Pi.

### 2. Se connecter au Pi en SSH

Depuis Windows, ouvrir **PowerShell**. Trouver l'adresse IP que le Pi a prise sur
le réseau (le filtre cible les adresses MAC des Raspberry) :

```powershell
arp -a | Select-String "b8-27-eb|dc-a6-32|e4-5f-01|d8-3a-dd|2c-cf-67|28-cd-c1"
```

> Astuce : pour coller dans PowerShell, faites un **clic droit** sur la ligne de
> commande.

Se connecter en remplaçant l'IP par celle obtenue ci-dessus :

```powershell
ssh minitel@192.168.1.42
```

Saisir le mot de passe défini à l'étape 1. C'est normal qu'**aucun caractère ne
s'affiche** pendant la frappe : c'est une sécurité.

### 3. Installer MINITEL GPT

Une fois connecté au Pi, mettre à jour le système et installer **git** (qui sert
ensuite à garder le Pi sur la dernière version) :

```bash
sudo apt update
sudo apt install git
```

Télécharger le projet :

```bash
cd /home/minitel
git clone https://github.com/jherard-fr/minitel-gpt.git
cd minitel-gpt
```

Lancer l'installation (dépendances + services systemd) :

```bash
sudo bash install.sh
```

Puis démarrer les services :

```bash
sudo systemctl restart minitel-chatgpt admin-ui wifi-manager
```

**Voilà, c'est fini.** L'écran d'accueil s'affiche sur le Minitel (sur un
**Minitel 2**, faire `Fnct + Sommaire` à chaque allumage). Il reste à saisir la
clé API depuis l'admin (étape 4).

Le script `install.sh` se charge de **tout** : paquets système, dépendance Python
`pyfiglet`, désactivation du `dnsmasq` système (conflit hotspot), groupe
`dialout` (accès au port série FTDI), création de `config/prompts.json` et d'un
`.env` par défaut s'ils manquent, règle sudo (l'admin redémarre les services), et
activation des 3 services systemd.

> Le dossier est un **clone git**, ce qui permet la mise à jour en un clic depuis
> l'admin (onglet **Paramètres**). Ne pas remplacer les fichiers à la main.

### 4. Renseigner la clé API

Aucun fichier à éditer à la main : ouvrir l'**admin web** (voir plus bas), onglet
**Paramètres**, choisir le **fournisseur d'IA** (**Mistral** ou **Claude**) et
coller la clé correspondante. Un menu propose pour chacun les modèles disponibles
avec leur coût et leur pertinence.

- Clé **Mistral** : <https://admin.mistral.ai/organization/api-keys>
- Clé **Claude** : <https://platform.claude.com/>

> Le `.env` (créé automatiquement par l'installation) peut aussi être édité
> directement, mais l'admin est plus simple. Variables disponibles :
> `LLM_PROVIDER` (`mistral` ou `claude`), `MISTRAL_KEY`, `MISTRAL_MODEL`,
> `ANTHROPIC_KEY`, `CLAUDE_MODEL`.

### Mettre à jour le code (après installation)

Le plus simple : depuis l'**admin web** → onglet **Paramètres** → *Vérifier les
mises à jour* puis *Mettre à jour maintenant* (voir [Mise à jour depuis
l'admin](#mise-à-jour-depuis-ladmin)).

En ligne de commande, c'est équivalent à :

```bash
cd /home/minitel/minitel-gpt
git pull
sudo systemctl restart minitel-chatgpt admin-ui wifi-manager
```

---

## Services systemd

| Service | Rôle |
|---|---|
| `minitel-chatgpt` | Terminal : lit le clavier Minitel, interroge l'IA (Mistral ou Claude), affiche la réponse paginée |
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

`http://<ip-du-pi>:8080` - mot de passe par défaut **mistral** (`ADMIN_PASSWORD`).

Trois onglets :
- **Tableau de bord** : état des services, activation des personnalités
- **Personnalités** : créer / modifier / supprimer des presets, génération de
  prompt par IA, **fichiers de connaissance** (.txt) injectés dans le contexte,
  textes d'accueil personnalisables, **zone de test** pour essayer les requêtes
  sans le Minitel (mêmes prompt, connaissances et fournisseur d'IA)
- **Paramètres** : choix du **fournisseur d'IA** (Mistral ou Claude) avec la clé
  et le modèle de chacun (coût + pertinence indiqués), **mise à jour de
  l'application**, logs

Les personnalités sont stockées dans `config/prompts.json`, leurs fichiers de
connaissance dans `config/knowledge/<personnalité>/`.

### Mise à jour depuis l'admin

L'onglet **Paramètres** permet de mettre à jour le code directement depuis
GitHub, sans manipulation SSH :

1. **Vérifier les mises à jour** → `git fetch` + affichage du changelog des
   nouveautés disponibles.
2. **Mettre à jour maintenant** → `git reset --hard origin/main` puis
   redémarrage automatique des services.
3. **Revenir à la version précédente** → rollback vers le commit d'avant.

Tes données locales ne sont **jamais** écrasées : `prompts.json` (personnalités),
`.env` (clés) et `config/knowledge/` sont hors du suivi git. Le dépôt fournit un
`config/prompts.default.json`, recopié seulement si `prompts.json` est absent.

> Prérequis : le dossier `~/minitel-gpt` du Pi doit être un **clone git** du dépôt
> (`git init` + `remote add origin` + `fetch` + `reset --hard origin/main`).

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
| Minitel 2 : écran d'accueil vide après `Fnct + Sommaire` | normal - appuyer sur `Sommaire` pour afficher MINITEL GPT |
| Affichage 80 colonnes qui défile sans pagination | Minitel 2 passé en mode téléinformatique via `Fnct + T A` - éviter cette combinaison (rester en `Fnct + Sommaire`) |
| Charabia à l'écran | vitesse Pi ≠ vitesse Minitel (rester à 1200 bauds des deux côtés) |
| Le hotspot n'apparaît pas | service `dnsmasq` système actif (port 53) → le désactiver |
| Caractères doublés à la saisie | écho local du Minitel + écho logiciel (ne pas ré-écho côté Pi) |
| Touches de fonction sans effet | Minitel 2 en mode téléinfo (touches VT100, gérées) ou octet `0x13` isolé (corrigé) |

---

*Projet personnel de Jérôme Hérard.*
