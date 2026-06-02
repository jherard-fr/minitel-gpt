#!/usr/bin/env python3
"""
Interface web d'administration — MinitelGPT
Accès : http://<ip-du-pi>:8080
Mot de passe : 13100
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from functools import wraps
from flask import (Flask, render_template_string, request, redirect,
                   url_for, session, jsonify)

PROJ_DIR = Path(__file__).parent.parent
PROMPTS_FILE = PROJ_DIR / "config" / "prompts.json"
LOGS_DIR = PROJ_DIR / "logs"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "13100")
SECRET_KEY = os.getenv("FLASK_SECRET", "minitel-secret-1985")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Helpers ────────────────────────────────────────────────────────────────

def load_prompts() -> dict:
    with open(PROMPTS_FILE) as f:
        return json.load(f)


def save_prompts(data: dict):
    with open(PROMPTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def restart_chatgpt():
    """Redémarre le service minitel-chatgpt."""
    result = subprocess.run(
        ["sudo", "systemctl", "restart", "minitel-chatgpt"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def service_status(name: str) -> str:
    r = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True, text=True
    )
    return r.stdout.strip()


def get_log_tail(name: str, lines: int = 30) -> str:
    log_file = LOGS_DIR / f"{name}.log"
    if not log_file.exists():
        return "(pas encore de log)"
    try:
        result = subprocess.run(
            ["tail", f"-{lines}", str(log_file)],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        return str(e)


# ── Templates ──────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MinitelGPT Admin</title>
<style>
  * { box-sizing: border-box; }
  body { background: #0d0d1a; color: #e0e0e0; font-family: 'Courier New', monospace;
    display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
  .box { background: #1a1a2e; border: 2px solid #00ff88; border-radius: 8px;
    padding: 40px; width: 340px; text-align: center; }
  h1 { color: #00ff88; font-size: 1.3em; margin-bottom: 4px; }
  .sub { color: #666; font-size: 0.8em; margin-bottom: 24px; }
  input { width: 100%; padding: 10px; background: #0d0d1a; border: 1px solid #00ff88;
    color: #e0e0e0; border-radius: 4px; font-family: monospace; font-size: 1.1em;
    letter-spacing: 0.2em; text-align: center; }
  button { width: 100%; margin-top: 12px; padding: 12px; background: #00ff88;
    color: #0d0d1a; border: none; border-radius: 4px; font-weight: bold;
    font-size: 1em; cursor: pointer; }
  button:hover { background: #00cc66; }
  .err { color: #ff4444; margin-top: 10px; font-size: 0.9em; }
  .logo { font-size: 2em; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="box">
  <div class="logo">🖥</div>
  <h1>MinitelGPT</h1>
  <div class="sub">Interface d'administration</div>
  <form method="POST">
    <input type="password" name="password" placeholder="••••••" autofocus autocomplete="off">
    <button type="submit">Entrer</button>
  </form>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
</div>
</body>
</html>"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MinitelGPT Admin</title>
<style>
  * { box-sizing: border-box; }
  body { background: #0d0d1a; color: #e0e0e0; font-family: 'Courier New', monospace; margin: 0; }
  header { background: #1a1a2e; border-bottom: 2px solid #00ff88; padding: 12px 24px;
    display: flex; justify-content: space-between; align-items: center; }
  header h1 { color: #00ff88; margin: 0; font-size: 1.2em; }
  .logout { color: #666; text-decoration: none; font-size: 0.85em; }
  .logout:hover { color: #ff4444; }
  main { max-width: 900px; margin: 0 auto; padding: 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
  .card { background: #1a1a2e; border: 1px solid #0f3460; border-radius: 8px; padding: 16px; }
  .card h2 { color: #00ff88; margin: 0 0 12px; font-size: 1em; }
  label { color: #aaa; font-size: 0.85em; display: block; margin-bottom: 4px; }
  select, input[type=text] { width: 100%; padding: 8px; background: #0d0d1a;
    border: 1px solid #0f3460; color: #e0e0e0; border-radius: 4px; font-family: monospace; }
  textarea { width: 100%; padding: 10px; background: #0d0d1a; border: 1px solid #0f3460;
    color: #e0e0e0; border-radius: 4px; font-family: monospace; font-size: 0.85em;
    resize: vertical; min-height: 200px; line-height: 1.5; }
  .btn { display: inline-block; padding: 8px 16px; border: none; border-radius: 4px;
    cursor: pointer; font-weight: bold; font-size: 0.9em; font-family: monospace; }
  .btn-primary { background: #00ff88; color: #0d0d1a; }
  .btn-primary:hover { background: #00cc66; }
  .btn-danger { background: #ff4444; color: white; }
  .btn-danger:hover { background: #cc0000; }
  .btn-secondary { background: #0f3460; color: #e0e0e0; border: 1px solid #00ff88; }
  .btn-secondary:hover { background: #1a4080; }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .active { background: #00ff88; }
  .inactive { background: #ff4444; }
  .status-row { display: flex; align-items: center; margin: 6px 0; font-size: 0.9em; }
  pre { background: #0d0d1a; padding: 10px; border-radius: 4px; font-size: 0.75em;
    overflow-x: auto; max-height: 200px; overflow-y: auto; color: #aaa; white-space: pre-wrap; }
  .flash { padding: 10px; border-radius: 4px; margin-bottom: 12px; font-size: 0.9em; }
  .flash.ok { background: #0d3320; color: #00ff88; border: 1px solid #00ff88; }
  .flash.err { background: #330d0d; color: #ff4444; border: 1px solid #ff4444; }
  .section-full { grid-column: 1 / -1; }
  .preset-label { font-size: 0.8em; color: #888; }
  .char-count { text-align: right; font-size: 0.75em; color: #666; margin-top: 4px; }
</style>
</head>
<body>
<header>
  <h1>🖥 MinitelGPT — Administration</h1>
  <a href="/logout" class="logout">Déconnexion</a>
</header>
<main>

{% if flash %}
<div class="flash {{ 'ok' if flash_ok else 'err' }}">{{ flash }}</div>
{% endif %}

<div class="grid">

  <!-- Statut services -->
  <div class="card">
    <h2>État des services</h2>
    {% for svc, st in services.items() %}
    <div class="status-row">
      <span class="status-dot {{ 'active' if st == 'active' else 'inactive' }}"></span>
      <span>{{ svc }}</span>
      <span style="margin-left:auto;color:{{ '#00ff88' if st == 'active' else '#ff4444' }}">{{ st }}</span>
    </div>
    {% endfor %}
    <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
      <form method="POST" action="/restart">
        <button class="btn btn-secondary" type="submit">↺ Redémarrer chatgpt</button>
      </form>
    </div>
  </div>

  <!-- Preset selector -->
  <div class="card">
    <h2>Preset rapide</h2>
    <form method="POST" action="/apply-preset">
      <label>Choisir un persona prédéfini</label>
      <select name="preset_key" onchange="updatePresetDesc(this)">
        {% for key, p in presets.items() %}
        <option value="{{ key }}" {{ 'selected' if key == active_key }}>{{ p.label }}</option>
        {% endfor %}
      </select>
      <p id="preset-desc" class="preset-label" style="margin-top:6px"></p>
      <button class="btn btn-primary" type="submit" style="margin-top:8px">Appliquer ce preset</button>
    </form>
  </div>

  <!-- Éditeur prompt -->
  <div class="card section-full">
    <h2>Prompt système actif — <span style="color:#aaa;font-size:0.85em">{{ active_label }}</span></h2>
    <form method="POST" action="/save-prompt">
      <label>Modifier le prompt (le sauvegarder redémarre le service Minitel)</label>
      <textarea name="system_prompt" id="promptTA" oninput="updateCount()">{{ active_prompt }}</textarea>
      <div class="char-count" id="charCount">0 caractères</div>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
        <button class="btn btn-primary" type="submit">💾 Sauvegarder et redémarrer</button>
        <button class="btn btn-secondary" type="button" onclick="resetPrompt()">✕ Annuler</button>
      </div>
    </form>
  </div>

  <!-- Logs chatgpt -->
  <div class="card section-full">
    <h2>Logs — minitel-chatgpt <a href="/logs/chatgpt" style="font-size:0.8em;color:#666;margin-left:8px">rafraîchir</a></h2>
    <pre id="logChatgpt">{{ log_chatgpt }}</pre>
  </div>

</div>
</main>

<script>
const origPrompt = {{ active_prompt | tojson }};
function updateCount() {
  const ta = document.getElementById('promptTA');
  document.getElementById('charCount').textContent = ta.value.length + ' caractères';
}
function resetPrompt() {
  document.getElementById('promptTA').value = origPrompt;
  updateCount();
}
updateCount();
</script>
</body>
</html>"""

# ── Routes ─────────────────────────────────────────────────────────────────

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
    active_key = data["active"]
    active = data["presets"].get(active_key, {})
    services = {
        "minitel-chatgpt": service_status("minitel-chatgpt"),
        "wifi-manager": service_status("wifi-manager"),
        "boot-notify": service_status("boot-notify"),
    }
    flash = session.pop("flash", None)
    flash_ok = session.pop("flash_ok", False)
    return render_template_string(
        ADMIN_HTML,
        presets=data["presets"],
        active_key=active_key,
        active_label=active.get("label", active_key),
        active_prompt=active.get("system", ""),
        services=services,
        log_chatgpt=get_log_tail("chatgpt"),
        flash=flash,
        flash_ok=flash_ok,
    )


@app.route("/apply-preset", methods=["POST"])
@require_login
def apply_preset():
    data = load_prompts()
    key = request.form.get("preset_key", "")
    if key in data["presets"]:
        data["active"] = key
        save_prompts(data)
        restart_chatgpt()
        session["flash"] = f"Preset '{data['presets'][key]['label']}' appliqué et service redémarré."
        session["flash_ok"] = True
    else:
        session["flash"] = "Preset inconnu."
        session["flash_ok"] = False
    return redirect(url_for("index"))


@app.route("/save-prompt", methods=["POST"])
@require_login
def save_prompt():
    data = load_prompts()
    new_prompt = request.form.get("system_prompt", "").strip()
    if not new_prompt:
        session["flash"] = "Prompt vide — non sauvegardé."
        session["flash_ok"] = False
        return redirect(url_for("index"))
    active_key = data["active"]
    data["presets"][active_key]["system"] = new_prompt
    save_prompts(data)
    restart_chatgpt()
    session["flash"] = "Prompt sauvegardé et service redémarré."
    session["flash_ok"] = True
    return redirect(url_for("index"))


@app.route("/restart", methods=["POST"])
@require_login
def restart():
    ok = restart_chatgpt()
    session["flash"] = "Service redémarré." if ok else "Échec redémarrage (sudo requis)."
    session["flash_ok"] = ok
    return redirect(url_for("index"))


@app.route("/logs/<name>")
@require_login
def logs(name: str):
    if name not in ("chatgpt", "wifi", "notify"):
        return "Log inconnu", 404
    content = get_log_tail(name, lines=50)
    return f"<pre style='background:#0d0d1a;color:#aaa;padding:20px;font-size:0.85em'>{content}</pre>"


@app.route("/api/status")
@require_login
def api_status():
    return jsonify({
        "chatgpt": service_status("minitel-chatgpt"),
        "wifi": service_status("wifi-manager"),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
