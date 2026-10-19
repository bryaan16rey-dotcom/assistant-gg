# Mari1565 y Sebas

El workflow se ejecuta manualmente desde GitHub Actions. Un observador
compartido lee el chat y detecta si sigue activo el reproductor. El audio para
transcripción llega por un puente privado desde el micrófono aislado en OBS;
no se transcribe el audio mezclado del reproductor. Mari y Sebas usan sesiones
independientes y solo escriben texto. Mari reconoce “Mari”,
“Mari1565”, “María”, “María Fernanda” y “Mafer”; Sebas reconoce “Sebas”,
“Sebastián”, “el Sebas” y “sebasdark”.

## Opciones al ejecutar

- **Personalidad:** se elige por separado para Mari y Sebas: `mixta` (predeterminada),
  `compa`, `tranquila`, `observadora` o `propia`. El estilo propio permite notas
  independientes para cada cuenta.
- **Interacción:** `natural` combina llamadas por nombre, menciones claras a un
  espectador y preguntas explícitas al chat. También puedes elegir `solo_mari`,
  `solo_sebas`, `named_viewer`, `open_chat`, `direct_chat` o `silent`.
- **Entradas y salidas:** cada ejecución elige tiempos variables. Mari entra
  2–5 minutos después de iniciar el workflow y permanece 50–65 minutos. Sebas
  entra 19–25 minutos después de Mari y permanece 50–65 minutos. El workflow
  tiene un máximo de 120 minutos para cubrir el peor caso y el arranque.
- **Turnos compartidos:** ambos reciben la misma transcripción reciente y las
  mismas filas del chat. Si Bryan nombra a uno, solo ese puede tomar el turno;
  si no nombra a ninguno, se alternan en preguntas abiertas. Antes de responder
  esperan 12 segundos y revisan los fragmentos de micrófono/chat que llegaron
  durante la espera. Si Bryan ya respondió,
  o ninguno puede aportar algo concreto, no escriben. No generan diálogo de
  relleno entre sí.
- **Frecuencia:** después de escribir, Mari espera un intervalo aleatorio de
  8–12 minutos antes de volver a intervenir; Sebas espera 13–17 minutos. Son
  pausas mínimas: si no hay algo pertinente, no mandan mensajes por cumplir un
  horario. Además hay al menos 3 minutos entre cualquier mensaje de ambos y un
  máximo compartido de 6, 12 o 18 mensajes cada seis horas (predeterminado 18).
  Estos límites se conservan mediante un artefacto de Actions. También se guardan
  hashes (no el texto) de los temas ya evaluados por seis horas, para reducir
  repeticiones entre ejecuciones manuales.
- **Fin del directo:** si el observador deja de detectar un video activo durante
  tres minutos consecutivos, cierra las sesiones. Una pausa larga del reproductor
  también puede activar este cierre; el resumen de Actions indica el motivo.
- **Resumen:** al terminar, Actions muestra el modo de ejecución, si se detectó
  actividad del stream, mensajes confirmados, borradores y omisiones recientes.
- **Seguir canal:** si está habilitado, cada cuenta pulsa `Seguir` solo si aún
  no sigue `bryan_`. En `dry_run`, no cambia el seguimiento.

Ambos bots son identificados en sus mensajes como `[Mari1565 · bot]` y
`[sebasdark · bot]`. Pueden devolverte un saludo breve si los saludas; no dan la
bienvenida al público, no hacen preguntas genéricas para llenar silencios y no
recitan normas ni moderan el chat. El estilo busca ser casual, pero no imita
literalmente a usuarios reales ni fuerza errores ortográficos.

La memoria temporal conserva hasta tres minutos de transcripción y de mensajes
nuevos del chat. Ignora lo que ya estaba visible al arrancar. La transcripción
usa solo la fuente que se conecte a la entrada `CABLE Output` del puente local;
por configuración, esa fuente será la monitorización exclusiva del micrófono
de OBS. No analiza la imagen ni debe afirmar que vio jugadas.

## Prueba de audio y envío

Haz la primera prueba mientras el directo esté activo, con `dry_run=true` y
`audio_source_validated=false`. La prueba abre ambas sesiones, pero no publica
ni cambia el seguimiento; termina cuando prepara el primer borrador o a los
cinco minutos. Los registros muestran solo el número de caracteres de una
transcripción y el conteo de borradores: nunca muestran las palabras habladas ni
el texto del borrador. En el resumen de Actions, confirma que hubo transcripción
y que se generó un borrador tras decir, por ejemplo, “Mari, es una prueba de
audio, ¿me saludas?”. Si el directo no está activo o no llega audio, la prueba
puede finalizar sin borrador.

Los fragmentos se transmiten cifrados por HTTPS, se guardan temporalmente en R2
hasta que el bot los transcribe y confirma, y no se guardan en el repositorio.
El Worker elimina fragmentos pendientes de más de dos minutos; configura además
la regla de retención de un día como respaldo. Si se oye otra fuente, deja
`audio_source_validated` desactivado y no hagas una ejecución normal. Antes de
la primera prueba, renueva las cookies de ambas cuentas si sus valores se
compartieron en capturas o mensajes; nunca las pegues en el chat.

El observador de lectura usa una página pública sin iniciar sesión. La prueba
debe confirmar que puede detectar reproducción y leer las filas del chat; el
audio ya no se toma de la página de Starvios.

## Conectar OBS con el puente privado

1. Instala VB-CABLE solo desde [VB-Audio](https://vb-audio.com/Cable/index.htm)
   y reinicia Windows si el instalador lo solicita.
2. En OBS abre **Ajustes → Audio → Avanzado** y selecciona **CABLE Input** como
   dispositivo de monitorización.
3. Abre **Editar → Propiedades de audio avanzadas**. En la fila **Micrófono**,
   selecciona **Monitorizar y salida**. En Audio de Roblox, Audio de Navegador,
   Alertas y cualquier otra fuente, deja **Monitorización desactivada**. Así el
   micrófono sigue llegando al stream y también al cable virtual; no monitorices
   el resto de fuentes hacia ese cable.
4. En Cloudflare, crea una cuenta si hace falta. Desde PowerShell, en la carpeta
   `cloudflare`, ejecuta:

   ```powershell
   npx wrangler login
   npx wrangler r2 bucket create assistant-gg-mic-audio
   npx wrangler deploy
   npx wrangler r2 bucket lifecycle add assistant-gg-mic-audio --expire-days 1
   ```

   Para generar el token aleatorio sin mostrarlo en pantalla, en PowerShell usa:

   ```powershell
   $tokenBytes = New-Object byte[] 32
   $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
   $rng.GetBytes($tokenBytes)
   $bridgeToken = [Convert]::ToBase64String($tokenBytes)
   Set-Clipboard $bridgeToken
   $rng.Dispose()
   ```

   Luego ejecuta `npx wrangler secret put AUDIO_BRIDGE_TOKEN` desde `cloudflare`
   y pega el token del portapapeles cuando lo solicite. Usa el mismo valor para
   crear el secreto `AUDIO_BRIDGE_TOKEN` en GitHub. Guarda también en GitHub el
   secreto `AUDIO_BRIDGE_URL` con la URL `workers.dev` que mostró `wrangler deploy`.
   Nunca pegues el token en el chat ni lo subas al repositorio; el programa local
   lo solicitará oculto al arrancar.
5. En PowerShell, desde la carpeta del proyecto, instala y lista los dispositivos:

   ```powershell
   py -m pip install -r requirements-audio-bridge.txt
   py audio_bridge.py --list-devices
   ```

   Debe aparecer `CABLE Output`. Después define la URL y el nombre del dispositivo,
   e inicia el puente. El script pedirá el token de forma oculta:

   ```powershell
   $env:AUDIO_BRIDGE_URL = "https://TU-WORKER.workers.dev"
   $env:AUDIO_INPUT_DEVICE = "CABLE Output"
   py audio_bridge.py
   ```

   Deja esa terminal abierta mientras haces la prueba `dry_run` de GitHub Actions.
   Detén el envío con Ctrl+C cuando termines el directo.

## Actions secrets requeridos

- `GROQ_API_KEY`
- `STARVIOS_SESSION_COOKIE` (Mari)
- `STARVIOS_SESSION_COOKIE_2` (Sebas)
- `CHAT_INPUT_SELECTOR`: campo de escritura del chat
- `CHAT_SEND_SELECTOR`: botón de envío
- `CHAT_MESSAGE_SELECTOR`: selector de cada fila del chat
- `CHAT_USERNAME_SELECTOR`: selector del autor dentro de cada fila
- `AUDIO_BRIDGE_URL`: URL HTTPS del Worker de Cloudflare
- `AUDIO_BRIDGE_TOKEN`: mismo token secreto configurado en el Worker

El workflow requiere permiso `actions: read` para leer el estado de frecuencia y
usa concurrencia para evitar ejecuciones simultáneas. Si no puede recuperar el
estado persistente, falla cerrado y no publica.
