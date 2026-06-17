#!/usr/bin/env python3
"""
Interface d'administration MINITEL GPT — http://<ip>:8080  (mot de passe 13100)
Navigation par onglets : Tableau de bord · Personnalités · Paramètres.
"""
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from functools import wraps
from flask import (Flask, render_template_string, request, redirect,
                   url_for, session, jsonify, send_from_directory)

PROJ_DIR = Path(__file__).parent.parent
ASSETS_DIR = PROJ_DIR / "assets"
PROMPTS_FILE = PROJ_DIR / "config" / "prompts.json"
ENV_FILE = PROJ_DIR / ".env"
LOGS_DIR = PROJ_DIR / "logs"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "13100")
SECRET_KEY = os.getenv("FLASK_SECRET", "minitel-secret-1985")

DEFAULTS = {
    "title_msg": "*** MINITEL GPT ***",
    "question_msg": "Posez votre question :",
    "loading_msg": "Consultation en cours...",
}

# Caractères affichés sur le Minitel → nettoyage ASCII (le Minitel ne gère pas
# les accents ni les caractères spéciaux). Appliqué à la sauvegarde des presets.
_ASCII_REPL = {
    "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "€": "EUR",
    "’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"',
    "–": "-", "—": "-", "…": "...", " ": " ", "·": ".",
}

def to_minitel_ascii(s: str) -> str:
    """Convertit un texte en ASCII pur affichable sur Minitel (sans accents)."""
    if not s:
        return s
    for k, v in _ASCII_REPL.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    return s.encode("ascii", "ignore").decode("ascii")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Helpers prompts ──────────────────────────────────────────────────────
def load_prompts():
    with open(PROMPTS_FILE) as f:
        return json.load(f)

def save_prompts(data):
    with open(PROMPTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalized_presets(data):
    out = {}
    for k, p in data["presets"].items():
        merged = dict(DEFAULTS)
        merged.update(p)
        merged.setdefault("system", "")
        merged.setdefault("label", k)
        out[k] = merged
    return out

# ── Helpers .env ─────────────────────────────────────────────────────────
def read_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def write_env_key(key, value):
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")

def mistral_key():
    return read_env().get("MISTRAL_KEY", os.getenv("MISTRAL_KEY", ""))

def mistral_model():
    return read_env().get("MISTRAL_MODEL", "mistral-small-latest")

# ── Auth ─────────────────────────────────────────────────────────────────
def require_login(f):
    @wraps(f)
    def d(*a, **k):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return d

# ── Services ─────────────────────────────────────────────────────────────
def restart_terminal():
    r = subprocess.run(["sudo", "systemctl", "restart", "minitel-chatgpt"],
                       capture_output=True, text=True)
    return r.returncode == 0

def svc_status(name):
    return subprocess.run(["systemctl", "is-active", name],
                          capture_output=True, text=True).stdout.strip()

def ip_address():
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout
        return out.split()[0] if out.split() else "?"
    except Exception:
        return "?"

def log_tail(name, n=40):
    f = LOGS_DIR / f"{name}.log"
    if not f.exists():
        return "(pas de log)"
    try:
        return subprocess.run(["tail", f"-{n}", str(f)],
                              capture_output=True, text=True).stdout
    except Exception as e:
        return str(e)

# ── Génération de prompt par IA ──────────────────────────────────────────
def generate_prompt(description):
    import requests
    key = mistral_key()
    if not key:
        raise RuntimeError("Clé Mistral absente")
    meta = (
        "Tu es expert en conception de prompts systeme pour un chatbot affiche "
        "sur un terminal Minitel (40 colonnes, ASCII sans accents ni emojis).\n\n"
        "A partir de la description ci-dessous, redige un prompt systeme complet "
        "en francais qui :\n"
        "1. Definit clairement le role, la personnalite et le ton du chatbot.\n"
        "2. Borne STRICTEMENT le chatbot au theme decrit (il refuse tout hors-sujet).\n"
        "3. Resiste aux tentatives de contournement, jailbreak ou changement de role.\n"
        "4. Impose des reponses concises (max 15 lignes de 40 caracteres), en ASCII "
        "sans accents.\n"
        "5. Donne 2-3 exemples de comportement attendu.\n\n"
        "Reponds UNIQUEMENT avec le texte du prompt systeme, sans preambule.\n\n"
        f"DESCRIPTION DU PROJET :\n{description}"
    )
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": mistral_model(), "max_tokens": 1500,
              "messages": [{"role": "user", "content": meta}]},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

# ── Templates ────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html><html lang=fr><head><meta charset=UTF-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>MinitelGPT Admin</title>
<link rel=icon type=image/png sizes=32x32 href=/assets/favicon-32.png>
<link rel=apple-touch-icon href=/assets/apple-touch-icon-180.png>
<style>body{background:#1b1b1f;color:#e6e6e6;font-family:'Courier New',monospace;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#26262b;border:1px solid #3a3a42;border-radius:12px;padding:36px;width:340px;text-align:center}
.logo-badge{background:#eceae3;border-radius:14px;padding:14px;display:inline-block;margin-bottom:18px}
.logo-badge img{width:180px;height:auto;display:block}
input{width:100%;padding:12px;background:#1b1b1f;border:1px solid #4ecdc4;color:#e6e6e6;border-radius:6px;text-align:center;letter-spacing:.2em;box-sizing:border-box;font-size:16px}
button{width:100%;margin-top:12px;padding:12px;background:#4ecdc4;color:#06201d;border:none;border-radius:6px;font-weight:bold;cursor:pointer;font-size:1em}
button:hover{background:#3db5ab}.err{color:#ff5b5b;margin-top:10px}</style></head><body>
<div class=box><div class=logo-badge><img src=/assets/logo-minitel-gpt.png alt="MINITEL GPT"></div>
<form method=POST><input type=password name=password placeholder="••••••" autofocus>
<button>Entrer</button></form>{% if error %}<div class=err>{{error}}</div>{% endif %}</div></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html lang=fr><head><meta charset=UTF-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>MinitelGPT Admin</title>
<link rel=icon type=image/png sizes=32x32 href=/assets/favicon-32.png>
<link rel=apple-touch-icon href=/assets/apple-touch-icon-180.png>
<style>
:root{--accent:#4ecdc4;--accent-d:#3db5ab;--bg:#1b1b1f;--bg2:#222227;--card:#26262b;
  --border:#3a3a42;--text:#e6e6e6;--muted:#9a9aa4;--danger:#ff5b5b}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Courier New',monospace;margin:0;padding-bottom:40px}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:12px 20px;
  background:var(--bg2);border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:12px}
.logo-badge{background:#eceae3;border-radius:10px;padding:6px 10px;display:inline-flex}
.logo-badge img{height:34px;width:auto;display:block}
.brand b{font-size:1.05em;color:var(--text)}
.logout{color:var(--muted);text-decoration:none;font-size:.85em}.logout:hover{color:var(--danger)}
nav.tabs{display:flex;gap:4px;max-width:920px;margin:18px auto 0;padding:0 20px;flex-wrap:wrap}
nav.tabs button{background:transparent;border:1px solid var(--border);border-bottom:none;
  color:var(--muted);padding:11px 20px;border-radius:8px 8px 0 0;cursor:pointer;font-family:inherit;font-size:.95em}
nav.tabs button.active{background:var(--card);color:var(--accent);border-color:var(--border);font-weight:bold}
main{max-width:920px;margin:0 auto;padding:0 20px}
.tabwrap{background:var(--card);border:1px solid var(--border);border-radius:0 10px 10px 10px;padding:20px}
.panel{display:none}.panel.active{display:block}
.block{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px;margin-bottom:16px}
.block:last-child{margin-bottom:0}
h2{color:var(--accent);margin:0 0 6px;font-size:1.1em}
h3{color:var(--accent);font-size:1em;margin:14px 0 6px}
.sub{color:var(--muted);font-size:.8em;margin:0 0 12px}
label{color:#b8b8c0;font-size:.85em;display:block;margin:10px 0 4px}
select,input[type=text],input[type=password],textarea{width:100%;padding:10px;background:var(--bg);
  border:1px solid var(--border);color:var(--text);border-radius:6px;font-family:monospace;font-size:15px}
select:focus,input:focus,textarea:focus{outline:none;border-color:var(--accent)}
textarea{resize:vertical;font-size:.85em;line-height:1.5}
.btn{padding:10px 18px;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:.9em;font-family:monospace;margin:8px 8px 0 0}
.btn-p{background:var(--accent);color:#06201d}.btn-p:hover{background:var(--accent-d)}
.btn-s{background:transparent;color:var(--accent);border:1px solid var(--accent)}.btn-s:hover{background:#16302e}
.btn-d{background:transparent;color:var(--danger);border:1px solid var(--danger)}.btn-d:hover{background:#2a1414}
.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.toolbar select{flex:1;min-width:180px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}
.on{background:var(--accent)}.off{background:#667}
.row{display:flex;align-items:center;margin:8px 0;font-size:.92em}
.plist{list-style:none;padding:0;margin:0}
.plist li{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid var(--border);
  border-radius:8px;margin-bottom:8px;background:var(--bg)}
.plist .name{flex:1}
.tag{background:#16302e;color:var(--accent);border:1px solid var(--accent);border-radius:20px;padding:2px 10px;font-size:.72em}
pre{background:var(--bg);padding:10px;border-radius:6px;font-size:.72em;max-height:280px;overflow:auto;color:#b8b8c0;white-space:pre-wrap}
.flash{padding:11px;border-radius:6px;margin:14px auto 0;max-width:920px;font-size:.9em}
.fok{background:#10302b;color:var(--accent);border:1px solid var(--accent)}
.ferr{background:#301414;color:var(--danger);border:1px solid var(--danger)}
#spin{display:none;color:var(--muted);margin-top:8px}
hr{border:none;border-top:1px solid var(--border);margin:16px 0}
.ipbox{font-size:.9em;color:var(--muted)}.ipbox b{color:var(--accent)}
</style></head><body>
<div class=topbar>
  <div class=brand><span class=logo-badge><img src=/assets/logo-minitel-gpt.png alt=""></span><b>Administration</b></div>
  <a href=/logout class=logout>Déconnexion</a>
</div>

{% if flash %}<div class="flash {{'fok' if flash_ok else 'ferr'}}">{{flash}}</div>{% endif %}

<nav class=tabs>
  <button data-tab=dash class=active>Tableau de bord</button>
  <button data-tab=perso>Personnalités</button>
  <button data-tab=params>Paramètres</button>
</nav>
<main><div class=tabwrap>

<!-- TABLEAU DE BORD -->
<section class="panel active" id=dash>
  <div class=block>
    <h2>État du Pi</h2>
    <p class=ipbox>Adresse : <b>http://{{ip}}:8080</b></p>
    {% for s,st in services.items() %}
    <div class=row><span class="dot {{'on' if st=='active' else 'off'}}"></span>{{s}}
      <span style="margin-left:auto;color:{{'#4ecdc4' if st=='active' else '#667'}}">{{st}}</span></div>
    {% endfor %}
    <form method=POST action=/restart style=margin-top:10px>
      <button class="btn btn-s">↺ Redémarrer le terminal</button></form>
    <p class=sub>« inactive » sur wifi/boot = normal (services ponctuels).</p>
  </div>
  <div class=block>
    <h2>Personnalités disponibles</h2>
    <p class=sub>La personnalité active est celle utilisée par le Minitel.</p>
    <ul class=plist>
      {% for k,p in presets.items() %}
      <li>
        <span class=name>{{p.label}}</span>
        {% if k==active_key %}<span class=tag>active</span>
        {% else %}
        <form method=POST action=/apply-preset style=margin:0>
          <input type=hidden name=preset_key value="{{k}}">
          <button class="btn btn-s" style=margin:0;padding:6px 12px>Activer</button>
        </form>
        {% endif %}
      </li>
      {% endfor %}
    </ul>
  </div>
</section>

<!-- PERSONNALITES (editeur) -->
<section class=panel id=perso>
  <div class=block>
    <h2>Éditeur de personnalités</h2>
    <div class=toolbar>
      <select id=presetSel onchange=loadPreset()>
        {% for k,p in presets.items() %}
        <option value="{{k}}" {{'selected' if k==active_key}}>{{p.label}}{{' (active)' if k==active_key else ''}}</option>
        {% endfor %}
      </select>
      <button class="btn btn-s" type=button onclick=newPreset() style=margin:0>+ Nouveau</button>
    </div>
    <p class=sub id=activeInfo></p>
    <form method=POST action=/save-prompt id=editForm>
      <input type=hidden name=preset_key id=fkey>
      <label>Nom affiché</label>
      <input type=text name=label id=flabel>
      <label>Titre d'accueil (max 40)</label>
      <input type=text name=title_msg id=ftitle maxlength=40>
      <label>Phrase d'invite (max 40)</label>
      <input type=text name=question_msg id=fquestion maxlength=40>
      <label>Message d'attente (max 40)</label>
      <input type=text name=loading_msg id=floading maxlength=40>
      <label>Prompt système (consignes de l'IA)</label>
      <textarea name=system_prompt id=fsystem rows=12></textarea>
      <hr>
      <button class="btn btn-p">💾 Enregistrer</button>
      <button class="btn btn-s" formaction=/apply-preset>✓ Activer</button>
      <button class="btn btn-d" formaction=/delete-preset onclick="return confirm('Supprimer ce preset ?')">Supprimer</button>
    </form>
  </div>
  <div class=block>
    <h2>✨ Générer un prompt par IA</h2>
    <p class=sub>Décrivez le projet : l'IA rédige les consignes, qui rempliront le champ « Prompt système » ci-dessus (éditable avant d'enregistrer).</p>
    <textarea id=desc rows=4 placeholder="Ex: Un assistant qui ne parle que de cuisine italienne, ton chaleureux, refuse tout autre sujet..."></textarea>
    <button class="btn btn-p" type=button onclick=genPrompt()>Générer les consignes</button>
    <div id=spin>⏳ Génération en cours...</div>
  </div>
</section>

<!-- PARAMETRES -->
<section class=panel id=params>
  <div class=block>
    <h2>Clé API Mistral</h2>
    <form method=POST action=/save-key>
      <p class=sub>Actuelle : {{key_masked}}</p>
      <input type=password name=mistral_key placeholder="clé Mistral...">
      <button class="btn btn-p">Enregistrer la clé</button>
    </form>
    <p class=sub style=margin-top:10px>Adresse de l'admin : consultable sur le Minitel via la touche <b>Guide</b>.</p>
  </div>
  <div class=block>
    <h2>Logs du terminal <a href=/ class=sub style=margin-left:8px>rafraîchir</a></h2>
    <pre>{{log_chatgpt}}</pre>
  </div>
</section>

</div></main>

<script>
const PRESETS = {{presets_json|safe}};
const ACTIVE = {{active_key|tojson}};
// Onglets
document.querySelectorAll('nav.tabs button').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('nav.tabs button').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById(b.dataset.tab).classList.add('active');
    localStorage.setItem('mgptTab', b.dataset.tab);
  };
});
(function(){const t=localStorage.getItem('mgptTab');
  if(t&&document.getElementById(t)){
    document.querySelectorAll('nav.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.tab===t));
    document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===t));
  }})();
// Editeur
function loadPreset(){
  const k=document.getElementById('presetSel').value, p=PRESETS[k]; if(!p)return;
  fkey.value=k; flabel.value=p.label||''; ftitle.value=p.title_msg||'';
  fquestion.value=p.question_msg||''; floading.value=p.loading_msg||''; fsystem.value=p.system||'';
  document.getElementById('activeInfo').textContent=
    (k===ACTIVE)?'● Personnalité actuellement active sur le Minitel.'
                :'Personnalité inactive. Cliquez « Activer » pour l\\'utiliser.';
}
function newPreset(){
  const label=prompt("Nom de la nouvelle personnalité :"); if(!label)return;
  const f=document.createElement('form');f.method='POST';f.action='/new-preset';
  const a=document.createElement('input');a.name='label';a.value=label;f.appendChild(a);
  const b=document.createElement('input');b.name='key';b.value=label.toLowerCase().replace(/[^a-z0-9]+/g,'_');f.appendChild(b);
  document.body.appendChild(f);localStorage.setItem('mgptTab','perso');f.submit();
}
async function genPrompt(){
  const d=document.getElementById('desc').value.trim();
  if(!d){alert('Décrivez le projet d abord');return;}
  spin.style.display='block';
  try{const r=await fetch('/generate-prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({description:d})});
    const j=await r.json();
    if(j.ok){fsystem.value=j.prompt;fsystem.scrollIntoView({behavior:'smooth'});}else alert('Erreur: '+j.error);
  }catch(e){alert('Erreur: '+e);}
  spin.style.display='none';
}
loadPreset();
</script>
</body></html>"""

# ── Routes ───────────────────────────────────────────────────────────────
@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Mot de passe incorrect"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@require_login
def index():
    data = load_prompts()
    presets = normalized_presets(data)
    key = mistral_key()
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else ("(définie)" if key else "(absente)")
    services = {"minitel-chatgpt": svc_status("minitel-chatgpt"),
                "wifi-manager": svc_status("wifi-manager"),
                "admin-ui": svc_status("admin-ui")}
    flash = session.pop("flash", None); flash_ok = session.pop("flash_ok", False)
    return render_template_string(
        ADMIN_HTML, presets=presets, presets_json=json.dumps(presets),
        active_key=data["active"], services=services, ip=ip_address(),
        log_chatgpt=log_tail("chatgpt"), key_masked=masked,
        flash=flash, flash_ok=flash_ok)

@app.route("/save-prompt", methods=["POST"])
@require_login
def save_prompt():
    data = load_prompts()
    k = request.form.get("preset_key", "").strip() or data["active"]
    p = data["presets"].setdefault(k, {})
    p["label"] = request.form.get("label", k).strip() or k
    p["title_msg"] = to_minitel_ascii(request.form.get("title_msg", DEFAULTS["title_msg"]))[:40]
    p["question_msg"] = to_minitel_ascii(request.form.get("question_msg", DEFAULTS["question_msg"]))[:40]
    p["loading_msg"] = to_minitel_ascii(request.form.get("loading_msg", DEFAULTS["loading_msg"]))[:40]
    sp = request.form.get("system_prompt", "").strip()
    if sp:
        p["system"] = sp
    save_prompts(data)
    if k == data["active"]:
        restart_terminal()
    session["flash"] = f"Personnalité '{p['label']}' enregistrée."
    session["flash_ok"] = True
    return redirect(url_for("index"))

@app.route("/apply-preset", methods=["POST"])
@require_login
def apply_preset():
    data = load_prompts()
    k = request.form.get("preset_key", "")
    if k in data["presets"]:
        p = data["presets"][k]
        if request.form.get("label"):
            p["label"] = request.form.get("label").strip()
            p["title_msg"] = to_minitel_ascii(request.form.get("title_msg", DEFAULTS["title_msg"]))[:40]
            p["question_msg"] = to_minitel_ascii(request.form.get("question_msg", DEFAULTS["question_msg"]))[:40]
            p["loading_msg"] = to_minitel_ascii(request.form.get("loading_msg", DEFAULTS["loading_msg"]))[:40]
            if request.form.get("system_prompt", "").strip():
                p["system"] = request.form.get("system_prompt").strip()
        data["active"] = k
        save_prompts(data)
        restart_terminal()
        session["flash"] = f"Personnalité '{p.get('label', k)}' activée."
        session["flash_ok"] = True
    return redirect(url_for("index"))

@app.route("/new-preset", methods=["POST"])
@require_login
def new_preset():
    data = load_prompts()
    key = re.sub(r"[^a-z0-9_]", "_", request.form.get("key", "").strip().lower())
    label = request.form.get("label", "").strip()
    if not key:
        session["flash"] = "Identifiant invalide."; session["flash_ok"] = False
    elif key in data["presets"]:
        session["flash"] = "Cet identifiant existe déjà."; session["flash_ok"] = False
    else:
        data["presets"][key] = {"label": label or key,
                                "system": "Tu es un assistant. Reponds en ASCII sans accents, concis.",
                                **DEFAULTS}
        save_prompts(data)
        session["flash"] = f"Personnalité '{label}' créée. Éditez-la puis Activez-la."
        session["flash_ok"] = True
    return redirect(url_for("index"))

@app.route("/delete-preset", methods=["POST"])
@require_login
def delete_preset():
    data = load_prompts()
    k = request.form.get("preset_key", "")
    if len(data["presets"]) <= 1:
        session["flash"] = "Impossible de supprimer la dernière personnalité."; session["flash_ok"] = False
    elif k in data["presets"]:
        del data["presets"][k]
        if data["active"] == k:
            data["active"] = next(iter(data["presets"]))
            save_prompts(data); restart_terminal()
        else:
            save_prompts(data)
        session["flash"] = "Personnalité supprimée."; session["flash_ok"] = True
    return redirect(url_for("index"))

@app.route("/generate-prompt", methods=["POST"])
@require_login
def gen_prompt_route():
    desc = (request.json or {}).get("description", "").strip()
    if not desc:
        return jsonify(ok=False, error="Description vide")
    try:
        return jsonify(ok=True, prompt=generate_prompt(desc))
    except Exception as e:
        return jsonify(ok=False, error=str(e))

@app.route("/save-key", methods=["POST"])
@require_login
def save_key():
    key = request.form.get("mistral_key", "").strip()
    if key:
        write_env_key("MISTRAL_KEY", key)
        restart_terminal()
        session["flash"] = "Clé Mistral enregistrée et terminal redémarré."
        session["flash_ok"] = True
    else:
        session["flash"] = "Clé vide."; session["flash_ok"] = False
    return redirect(url_for("index"))

@app.route("/restart", methods=["POST"])
@require_login
def restart():
    ok = restart_terminal()
    session["flash"] = "Terminal redémarré." if ok else "Échec (sudo requis)."
    session["flash_ok"] = ok
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
