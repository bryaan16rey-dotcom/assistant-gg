# pip install flask
import statistics
import time
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, render_template_string, request

app = Flask(__name__)
SESIONES = {}   # sid -> datos de la sesión
MENSAJES = []   # mensajes del chat

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{{ titulo }}</title>
<style>
body { font-family: sans-serif; max-width: 700px; margin: 20px auto; min-height: 1600px; }
#mensajes { border: 1px solid #888; height: 160px; overflow-y: auto; padding: 6px; margin-bottom: 6px; }
</style></head><body>
<h1>{{ titulo }}</h1>
<nav>
  <a id="inicio" href="/">Inicio</a> |
  <a id="acerca" href="/acerca">Acerca</a> |
  <a id="contacto" href="/contacto">Contacto</a> |
  <a href="/visitas">Ver visitas</a>
</nav>
<p>Página de prueba para la clase de ciberseguridad. Baja para ver el chat.</p>
<div style="height:500px"></div>
<h3>Chat</h3>
<div id="mensajes"></div>
<input id="nombre" placeholder="nombre" size="10">
<input id="texto" placeholder="mensaje" size="35">
<button id="enviar">Enviar</button>

<script>
// ---- Telemetría: el servidor usa esto para decidir si es bot o humano ----
const t = { mouse: 0, clicks: 0, scrolls: 0, keys: 0, intervalos: [], webdriver: !!navigator.webdriver };
let ultima = 0;
document.addEventListener('mousemove', () => t.mouse++);
document.addEventListener('click', () => t.clicks++);
window.addEventListener('scroll', () => t.scrolls++);
document.addEventListener('keydown', () => {
  const ahora = performance.now();
  if (ultima && ahora - ultima < 3000) t.intervalos.push(Math.round(ahora - ultima));
  ultima = ahora;
  t.keys++;
});
function enviarTelemetria() {
  const datos = JSON.stringify(t);
  t.mouse = 0; t.clicks = 0; t.scrolls = 0; t.keys = 0; t.intervalos = [];
  fetch('/api/telemetria', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: datos, keepalive: true }).catch(() => {});
}
setInterval(enviarTelemetria, 2000);
window.addEventListener('pagehide', enviarTelemetria);

// ---- Chat ----
const caja = document.getElementById('mensajes');
async function cargar() {
  try {
    const r = await fetch('/api/chat');
    const lista = await r.json();
    caja.textContent = '';
    for (const m of lista) {
      const d = document.createElement('div');
      d.textContent = m.hora + ' ' + m.nombre + ': ' + m.texto;
      caja.appendChild(d);
    }
    caja.scrollTop = caja.scrollHeight;
  } catch (e) {}
}
async function enviar() {
  const texto = document.getElementById('texto');
  const nombre = document.getElementById('nombre');
  if (!texto.value.trim()) return;
  await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre: nombre.value || 'anonimo', texto: texto.value })
  });
  texto.value = '';
  cargar();
}
document.getElementById('enviar').addEventListener('click', enviar);
document.getElementById('texto').addEventListener('keydown', e => { if (e.key === 'Enter') enviar(); });
cargar();
setInterval(cargar, 2000);
</script>
</body></html>
"""

TABLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta http-equiv="refresh" content="3">
<title>Visitas</title>
<style>table{border-collapse:collapse}td,th{border:1px solid #888;padding:4px 8px;font-size:14px}</style>
</head><body>
<h1>Sesiones ({{ filas|length }})</h1>
<table>
<tr><th>Sesión</th><th>Páginas</th><th>Mouse</th><th>Teclas</th><th>Msgs</th>
<th>Capa 1: comportamiento</th><th>Capa 2: huella del navegador</th><th>Veredicto</th><th>User-Agent</th></tr>
{% for f in filas %}
<tr><td>{{ f.sid }}</td><td>{{ f.paginas }}</td><td>{{ f.mouse }}</td><td>{{ f.keys }}</td>
<td>{{ f.mensajes }}</td><td>{{ f.capa1 }}</td><td>{{ f.capa2 }}</td>
<td><b>{{ f.veredicto }}</b></td><td>{{ f.ua }}</td></tr>
{% endfor %}
</table></body></html>
"""


def nueva_sesion():
    ahora = time.time()
    return {"inicio": ahora, "ultima": ahora, "ua": "", "paginas": [],
            "mouse": 0, "clicks": 0, "scrolls": 0, "keys": 0, "intervalos": [],
            "mensajes": 0, "webdriver": False, "puntos_headers": 0}


def puntos_headers(req):
    puntos = 0
    ua = req.headers.get("User-Agent", "").lower()
    if not ua:
        puntos += 3
    if "headless" in ua:
        puntos += 3
    if any(x in ua for x in ("bot", "crawler", "spider", "python", "curl")):
        puntos += 3
    if not req.headers.get("Accept-Language"):
        puntos += 2
    return puntos


def evaluar(s):
    """Devuelve (puntos de comportamiento, puntos de huella)."""
    comp = s["puntos_headers"]
    tiempo = s["ultima"] - s["inicio"]
    n_pag = len(s["paginas"])
    if tiempo > 6 and s["mouse"] == 0:
        comp += 3                      # nunca movió el mouse
    iv = s["intervalos"]
    if len(iv) >= 8 and statistics.pstdev(iv) < 15:
        comp += 3                      # teclea con ritmo demasiado regular
    if n_pag >= 3 and s["scrolls"] == 0:
        comp += 1                      # navega sin hacer scroll
    if n_pag >= 3 and tiempo / n_pag < 2:
        comp += 2                      # salta de página demasiado rápido
    huella = 4 if s["webdriver"] else 0  # navigator.webdriver activo
    return comp, huella


@app.before_request
def preparar():
    g.sid = request.cookies.get("sid") or uuid.uuid4().hex[:8]
    if request.path in ("/favicon.ico", "/visitas"):
        return
    s = SESIONES.setdefault(g.sid, nueva_sesion())
    s["ultima"] = time.time()
    if not request.path.startswith("/api"):
        s["paginas"].append(request.path)
        s["ua"] = request.headers.get("User-Agent", "(vacío)")
        s["puntos_headers"] = max(s["puntos_headers"], puntos_headers(request))


@app.after_request
def poner_cookie(resp):
    if not request.cookies.get("sid"):
        resp.set_cookie("sid", g.sid)
    return resp


def pagina(titulo):
    return render_template_string(PAGINA, titulo=titulo)


@app.route("/")
def inicio():
    return pagina("Inicio")


@app.route("/acerca")
def acerca():
    return pagina("Acerca")


@app.route("/contacto")
def contacto():
    return pagina("Contacto")


@app.route("/api/telemetria", methods=["POST"])
def telemetria():
    d = request.get_json(silent=True) or {}
    s = SESIONES.get(g.sid)
    if s:
        for k in ("mouse", "clicks", "scrolls", "keys"):
            s[k] += int(d.get(k, 0) or 0)
        nuevos = [int(x) for x in d.get("intervalos", [])]
        s["intervalos"] = (s["intervalos"] + nuevos)[-200:]
        s["webdriver"] = s["webdriver"] or bool(d.get("webdriver"))
    return jsonify(ok=True)


@app.route("/api/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        texto = str(d.get("texto", ""))[:200].strip()
        nombre = str(d.get("nombre", "anonimo"))[:20]
        if texto:
            MENSAJES.append({"hora": datetime.now().strftime("%H:%M:%S"),
                             "nombre": nombre, "texto": texto})
            s = SESIONES.get(g.sid)
            if s:
                s["mensajes"] += 1
        return jsonify(ok=True)
    return jsonify(MENSAJES[-50:])


@app.route("/visitas")
def visitas():
    filas = []
    for sid, s in SESIONES.items():
        comp, huella = evaluar(s)
        capa1 = "BOT" if comp >= 3 else "humano"
        capa2 = "automatizado" if huella else "normal"
        filas.append({
            "sid": sid, "paginas": len(s["paginas"]), "mouse": s["mouse"],
            "keys": s["keys"], "mensajes": s["mensajes"],
            "capa1": f"{capa1} ({comp})", "capa2": capa2,
            "veredicto": "BOT" if (comp >= 3 or huella) else "humano",
            "ua": s["ua"],
        })
    return render_template_string(TABLA, filas=filas)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
