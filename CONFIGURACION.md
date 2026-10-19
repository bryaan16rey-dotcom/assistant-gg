# Configuración del bot

El workflow no se ejecuta por horario. Inícialo manualmente desde GitHub Actions
cuando estés transmitiendo. El navegador intenta capturar el audio del elemento
`<video>` del directo en fragmentos de 15 segundos y Groq Whisper los convierte
en texto. `listen_minutes` permite elegir de 1 a 180 minutos (1 por defecto).
Cada ejecución publica como máximo un mensaje. La primera prueba queda en modo
seguro: `dry_run=true` y `listen_minutes=1` por defecto.

En GitHub, configura estos Actions secrets:

- `GROQ_API_KEY`
- `STARVIOS_SESSION_COOKIE`
- `CHAT_INPUT_SELECTOR`: campo de escritura del chat
- `CHAT_SEND_SELECTOR`: botón para enviar
- `CHAT_MESSAGE_SELECTOR`: selector de cada mensaje individual del chat
- `CHAT_USERNAME_SELECTOR`: selector de los nombres de usuario visibles en el chat

Los selectores deben obtenerse de la interfaz de Starvios con sesión iniciada.
`CHAT_MESSAGE_SELECTOR` debe incluir el autor y el texto de cada fila, y
`CHAT_USERNAME_SELECTOR` debe seleccionar el nombre del autor, no el mensaje.
El bot solo considera responder si una transcripción menciona literalmente a
un usuario visible del chat; ante ambigüedad no publica.

La captura de audio solo funcionará si Chromium puede acceder al audio del
reproductor. Si Starvios usa un reproductor enmarcado, protegido o que no expone
una pista capturable, la ejecución lo indicará y no enviará mensajes. En ese
caso se necesitaría una fuente de audio autorizada alternativa; no se intenta
eludir protecciones del reproductor. El audio se envía a Groq para transcripción
y no se guarda como archivo en el repositorio.

Al iniciar el workflow, `dry_run` está activado por defecto. Déjalo así para
validar captura, transcripción y campo de chat sin enviar; solo desactívalo
después de revisar el primer borrador. El envío se confirma solo cuando el
texto aparece en el chat. Los artefactos de diagnóstico pueden contener
contenido visible del directo.
