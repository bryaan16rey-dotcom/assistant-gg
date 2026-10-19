# Mari1565 y Sebas: prueba de audio

El workflow se inicia manualmente en GitHub Actions y dura hasta 60 minutos.
Cada bot configurado usa una sesión independiente de Supabase y escribe en su
propia cuenta. Puedes empezar con una sola cuenta y añadir la otra después.
Para esta versión no se manda video ni capturas a Groq: el contexto hablado
proviene únicamente del micrófono que OBS envía a VB-CABLE. El bot también lee
los mensajes visibles del chat para entender a quién respondes; no procesa la
imagen del directo.

## Cómo se comportan

- Mari reconoce “Mari”, “Mari1565”, “María”, “María Fernanda” y “Mafer”. Sebas
  reconoce “Sebas”, “Sebastián”, “el Sebas” y “sebasdark”.
- Los bots configurados comparten transcripción reciente y chat. Si llamas a uno
  por su nombre, solo ese toma el turno; si ya respondiste, no repiten la respuesta.
- El estilo casual evita saludos genéricos al público, mensajes de bienvenida y
  moderación. Cada bot se identifica como una cuenta automatizada.
- Mari espera normalmente 8–12 minutos entre mensajes; Sebas 13–17 minutos.
  Además hay al menos 3 minutos entre mensajes de cualquiera y un límite
  compartido configurable de 6, 12 o 18 mensajes cada seis horas (por defecto 18).
- El workflow muestra horarios aleatorios de entrada y salida. Si hay dos
  cuentas, Mari entra 2–5 minutos después de iniciar y Sebas 19–25 minutos
  después de Mari. Si solo hay una, ese bot entra 2–5 minutos después de iniciar
  y permanece 50–65 minutos.
- En `dry_run`, puede leer el chat y preparar un borrador, pero no publica.
  Mantén `audio_source_validated=false` hasta confirmar que solo se transcribe
  tu voz.
- Las cuentas se identifican como automatizadas en cada mensaje. No se automatiza
  el seguimiento ni se simula actividad humana: los términos de Starvios prohíben
  inflar seguidores con bots o cuentas falsas.

## Privacidad y límites del puente temporal

El micrófono se envía desde tu PC mediante un **Cloudflare Quick Tunnel** a un
pequeño servidor local. El túnel genera una URL temporal `trycloudflare.com`;
no requiere R2, dominio ni cuenta de Cloudflare y está pensado para pruebas,
no para producción. La URL cambia cada vez que reinicias el túnel. Cualquiera
que conozca esa URL puede alcanzar el servicio, pero los endpoints de audio
requieren `AUDIO_BRIDGE_TOKEN`. No publiques la URL ni el token. La cola vive
solo en memoria y conserva como máximo 24 fragmentos de cinco segundos; lo más
antiguo se descarta si Actions se retrasa. El audio no se escribe a disco ni se
almacena en R2.

El bot transcribe el audio con Groq; las imágenes del directo no se envían a
ningún modelo. Las palabras transcritas y borradores no aparecen en los logs
públicos de Actions. La URL temporal se introduce como entrada del workflow y
`AUDIO_BRIDGE_TOKEN` permanece como GitHub Actions secret.

Las sesiones configuradas se guardan como secretos de GitHub. Contienen tokens
de acceso y de renovación: no las pegues en el chat, en un issue ni en un
archivo del repositorio. Si una sesión se filtra, ciérrala desde Starvios y
exporta una nueva.

## 1. Instalar VB-CABLE y aislar el micrófono en OBS

1. Descarga VB-CABLE desde [VB-Audio](https://vb-audio.com/Cable/index.htm),
   instala el controlador y reinicia Windows si el instalador lo pide.
2. En OBS abre **Ajustes → Audio → Avanzado** y elige **CABLE Input** como
   dispositivo de monitorización.
3. En OBS abre **Editar → Propiedades de audio avanzadas**. En la fila
   **Micrófono**, selecciona **Monitorizar y salida**. En **Audio de Roblox**,
   **Audio de Navegador**, **Alertas** y cualquier otra fuente, selecciona
   **Monitorización desactivada**. Esto no quita esas fuentes del stream: evita
   que entren al cable de monitorización.
4. La aplicación escucha el extremo de grabación **CABLE Output**. No cambies la
   salida predeterminada de Windows al cable. Confirma en el mezclador de OBS que
   el medidor del micrófono se mueve cuando hablas.

La guía de OBS describe el dispositivo de monitorización y las propiedades
avanzadas [aquí](https://obsproject.com/kb/video-call-streaming-tutorial/);
el manual de [VB-CABLE](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf)
explica la conexión entre CABLE Input y CABLE Output.

## 2. Preparar el secreto del puente

En GitHub, en **Settings → Secrets and variables → Actions**, crea el secret
`AUDIO_BRIDGE_TOKEN` con un valor aleatorio de al menos 32 caracteres. Puedes
generarlo en PowerShell y copiarlo sin imprimirlo:

```powershell
$tokenBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($tokenBytes)
$bridgeToken = [Convert]::ToBase64String($tokenBytes)
Set-Clipboard $bridgeToken
$rng.Dispose()
```

Pega el valor del portapapeles como secret de GitHub. El mismo valor se pide de
forma oculta cuando inicies `audio_bridge.py`; no lo pegues en el chat ni lo
incluyas en una URL.

## 3. Iniciar el servidor local y el túnel

Instala `cloudflared` desde las [descargas oficiales de Cloudflare](https://developers.cloudflare.com/tunnel/downloads/).
Abre dos ventanas de PowerShell o CMD desde la carpeta del proyecto.

En la primera ventana:

```powershell
cd C:\Users\b1676\Desktop\bot
py -m pip install -r requirements-audio-bridge.txt
py audio_bridge.py --list-devices
py audio_bridge.py
```

Cuando lo solicite, pega el valor de `AUDIO_BRIDGE_TOKEN` de forma oculta. Debe
detectar `CABLE Output`; deja esta ventana abierta.

En la segunda ventana inicia el túnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

Deja la ventana abierta y copia la URL `https://....trycloudflare.com` que
imprime `cloudflared`. No añadas rutas como `/v1/audio`.

## 4. Ejecutar la prueba de oro

1. Inicia tu directo y verifica que OBS recibe solo el micrófono en el cable.
2. En GitHub abre **Actions → Starvios chat bot → Run workflow**.
3. Para la primera prueba usa `dry_run=true` y `audio_source_validated=false`;
   pega la URL temporal completa en `audio_bridge_url`. Si solo tienes la cuenta
   de Mari, elige `interaction_mode=solo_mari` para que la prueba no dependa de
   la cuenta de Sebas. Si tienes las dos, puedes usar `natural`.
4. Di una frase clara, por ejemplo: “Mari, esto es una prueba de audio”.
   Comprueba en Actions que recibe transcripción y genera un borrador; el texto
   no se revela en los logs y no se publica ningún mensaje.
5. Si llega audio de juego, navegador o alertas, detén la prueba y corrige la
   monitorización antes de validar la fuente.

Al terminar, detén el túnel y el puente con **Ctrl+C**. La próxima vez inicia
un túnel nuevo y vuelve a pegar su nueva URL en el workflow. Para publicar en
una ejecución posterior, primero valida el audio en `dry_run`; no desactives el
modo seguro hasta revisar el resultado.

## Cuentas propias y login automático

La forma recomendada es que cada bot tenga su propia cuenta de Starvios y que
el workflow inicie sesión con email y contraseña al comenzar cada ejecución.
Así la sesión es nueva y no dependes de reexportar cookies.

Crea estos secretos en GitHub:

- Mari: `STARVIOS_EMAIL_MARI` y `STARVIOS_PASSWORD_MARI`
- Sebas: `STARVIOS_EMAIL_SEBAS` y `STARVIOS_PASSWORD_SEBAS`

Puedes empezar con una sola cuenta. Si solo configuras Mari, el bot funciona
solo con Mari; si solo configuras Sebas, solo con Sebas. Deja vacíos los
secretos del bot que no uses. El modo `natural` usa todas las cuentas
configuradas; `solo_mari` y `solo_sebas` exigen esa cuenta e ignoran por
completo la otra, aunque quede una sesión vieja guardada.

El bot inicia sesión con el formulario propio de Starvios usando el email y la
contraseña de la cuenta. Si el formulario no completa la sesión, intenta la API
de Supabase y, por último, el JSON de sesión guardado. La cuenta debe tener el
correo confirmado. Si tiene verificación en dos pasos, el login automático puede
rechazarse; en ese caso usa el JSON de sesión como respaldo. En `dry_run`, el bot
abre las sesiones configuradas al inicio, así puedes comprobar cada cuenta antes
de publicar.

Usa cuentas dedicadas a los bots, con contraseñas únicas y sin datos de pago ni
personales. Los secretos de GitHub están cifrados, pero cualquier workflow con
acceso a ellos puede leerlos; no reutilices una cuenta personal. El bot nunca
imprime la contraseña. No envíes contraseñas por chats, issues ni correos: si una
contraseña se comparte fuera de GitHub Secrets, cámbiala antes de usarla.

Las cuentas deben seguir identificándose como automatizadas. No se automatiza el
seguimiento de canales ni se simula actividad humana para ocultar que son bots.

## Respaldo: exportar la sesión de Starvios

Si no quieres guardar contraseñas, o si la cuenta tiene 2FA, puedes usar el JSON
de sesión. Starvios no autentica el chat con una cookie llamada `session`. Es una
aplicación de Supabase y guarda la sesión en la clave de `localStorage`
`sb-naiijcvngtkkocligwvk-auth-token`. Por eso el bot inyecta esa sesión antes
de cargar la página; una cookie del navegador no sirve.

Para cada cuenta, en un perfil de Chrome distinto (o en una ventana de
incógnito separada):

1. Entra en `https://starvios.com/auth` e inicia sesión con la cuenta.
2. Abre **DevTools → Console**.
3. Ejecuta este comando para copiar el JSON completo al portapapeles:

   ```js
   copy(localStorage.getItem('sb-naiijcvngtkkocligwvk-auth-token'))
   ```

4. Pega el valor en el secret correspondiente:
   - Mari: `STARVIOS_SESSION_COOKIE`
   - Sebas: `STARVIOS_SESSION_COOKIE_2`

El valor debe empezar por `{"access_token":...` e incluir `refresh_token` y
`user`. No pegues solo el token, una cookie ni el nombre de la clave. Si
configuras dos cuentas, sus sesiones deben ser distintas; si son iguales, ambas
publicarían como la misma persona.

La sesión incluye un token de renovación y Supabase puede renovarla durante la
ejecución. Aun así, Starvios puede revocarla o rotar el token; si una ejecución
falla con “no se ve el campo de chat”, vuelve a iniciar sesión y exporta un JSON
nuevo. No escribas contraseñas ni tokens en el repositorio ni en el YAML: usa
siempre GitHub Secrets.

## GitHub Actions secrets requeridos

- `GROQ_API_KEY`
- `CHAT_INPUT_SELECTOR`
- `CHAT_SEND_SELECTOR`
- `CHAT_MESSAGE_SELECTOR`
- `CHAT_USERNAME_SELECTOR`
- `AUDIO_BRIDGE_TOKEN`
- Mari: `STARVIOS_EMAIL_MARI` + `STARVIOS_PASSWORD_MARI`
- Sebas: `STARVIOS_EMAIL_SEBAS` + `STARVIOS_PASSWORD_SEBAS`

Puedes configurar solo una de las dos parejas. Deja vacíos los secretos del bot
que no uses. Como respaldo, en lugar de las credenciales de una cuenta puedes
configurar:

- `STARVIOS_SESSION_COOKIE` (JSON de localStorage de Mari)
- `STARVIOS_SESSION_COOKIE_2` (JSON de localStorage de Sebas)

Si existen email/contraseña y también sesión, se intenta primero el login con
contraseña y la sesión se usa solo si ese login falla.

La URL `AUDIO_BRIDGE_URL` no es un secret permanente: se pasa como entrada
`audio_bridge_url` en cada ejecución porque el Quick Tunnel es temporal.
