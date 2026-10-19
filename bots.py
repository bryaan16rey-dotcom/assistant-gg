import asyncio
import os
import random
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Error as PlaywrightError
from groq import Groq

# 1. Cargamos credenciales de forma segura desde los Secrets de GitHub
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
STARVIOS_SESSION_COOKIE = os.environ.get("STARVIOS_SESSION_COOKIE")

if not GROQ_API_KEY:
    raise SystemExit("Falta configurar la variable GROQ_API_KEY en GitHub Secrets.")

client = Groq(api_key=GROQ_API_KEY)

URL = "https://starvios.com/live/bryan_"
HOSTS_PERMITIDOS = {"starvios.com", "www.starvios.com"}

if urlparse(URL).hostname not in HOSTS_PERMITIDOS:
    raise SystemExit("Host no autorizado.")

INIT_SCRIPT = """
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false, configurable: true });
"""

HEADLESS = True  # En la nube SIEMPRE debe estar en True (sin interfaz gráfica)

async def pausa(pagina, a, b):
    try:
        await pagina.wait_for_timeout(random.randint(a, b))
    except PlaywrightError:
        pass

async def mover_y_escribir(pagina, selector_input, texto):
    try:
        locator = pagina.locator(selector_input).first
        if await locator.count() == 0:
            return False
        
        await locator.click()
        await pausa(pagina, 200, 500)
        await locator.fill("")
        for c in texto:
            await pagina.keyboard.type(c)
            await pausa(pagina, 40, 120)
            
        await pausa(pagina, 300, 600)
        await pagina.keyboard.press("Enter")
        return True
    except PlaywrightError:
        return False

async def obtener_contexto_stream(pagina):
    try:
        titulo_stream = await pagina.locator("h1").first.inner_text()
        return f"Stream actual de bryan_. Título/Info: {titulo_stream}"
    except Exception:
        return "Transmisión en vivo de bryan_ en Starvios jugando Dota 2."

async def generar_comentario_groq(contexto_pagina):
    system_prompt = (
        "Eres un espectador real en Starvios, peruano, súper activo y fanático de Dota 2. "
        "Estás viendo en vivo el canal de 'bryan_'. "
        "REGLAS ESTRICTAS DE PERSONALIDAD Y DIÁLOGO:\n"
        "- Hablas con jerga peruana y dotera natural, variada y fluida (ej. 'mano', 'causa', 'habla barrio', "
        "'gAAAA', 'asumare', 'feedear', 'manco', 'carry', 'gg izi', 'tranqui nomás', 'firme', 'que fueee', 'pipipi').\n"
        "- VOCABULARIO AMPLIO: Evita clichés robóticos como 'Hola a todos'. Varía siempre tus oraciones y expresiones.\n"
        "- Anima el stream de Bryan: Apoya sus jugadas ('buena Bryan', 'esa jugada fina', 'ala mela qué tal partida'), "
        "o coméntale al chat sobre lo que pasa.\n"
        "- Responde directamente basándote en el contexto actual del stream y del chat.\n"
        "- Escribe mensajes reales de chat de streaming: de 1 a 2 líneas cortas o medianas, espontáneos y con buena vibra."
    )
    user_prompt = f"Contexto actual del stream/chat: {contexto_pagina}. Escribe un mensaje corto, variado y espontáneo para el chat."

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=60,
        )
        return completion.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        print(f"⚠️ Error conectando con Groq: {e}")
        return "buena partida manito"

async def ciclo_bot():
    async with async_playwright() as p:
        navegador = await p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        contexto = await navegador.new_context(
            viewport={"width": 1366, "height": 768},
            locale="es-PE",
            timezone_id="America/Lima"
        )
        
        # Inyectamos la cookie de sesión de Starvios de manera segura
        if STARVIOS_SESSION_COOKIE:
            await contexto.add_cookies([{
                "name": "session",  # Nombre de la cookie de sesión de Starvios
                "value": STARVIOS_SESSION_COOKIE,
                "domain": ".starvios.com",
                "path": "/"
            }])

        await contexto.add_init_script(INIT_SCRIPT)
        pagina = await contexto.new_page()

        print(f"🚀 Conectando a {URL} desde la nube (GitHub Actions)...")
        try:
            await pagina.goto(URL, wait_until="domcontentloaded")
        except PlaywrightError:
            return
            
        await pausa(pagina, 4000, 6000)

        print("🤖 Analizando stream con Groq...")
        contexto_actual = await obtener_contexto_stream(pagina)
        frase_ia = await generar_comentario_groq(contexto_actual)
        
        selector_input = 'input[placeholder*="mensaje"], input[placeholder*="Chat"], textarea, div[contenteditable="true"]'
        exito = await mover_y_escribir(pagina, selector_input, frase_ia)
        
        if exito:
            print(f"💬 [IA en Chat]: {frase_ia}")
        else:
            print("⚠️ No se encontró la caja de texto para escribir el mensaje.")
        
        await pausa(pagina, 5000, 8000)
        await navegador.close()
        print("✅ Ejecución en la nube finalizada con éxito.")

if __name__ == "__main__":
    asyncio.run(ciclo_bot())
