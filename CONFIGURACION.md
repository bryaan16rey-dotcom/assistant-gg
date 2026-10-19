# Configuración del bot

El workflow no se ejecuta por horario. Inícialo manualmente desde GitHub Actions
cuando estés transmitiendo. Cada ejecución puede publicar como máximo un
mensaje. Groq puede responder `SKIP`; si no hay subtítulos o una respuesta útil,
no se publica nada.

En GitHub, configura estos Actions secrets:

- `GROQ_API_KEY`
- `STARVIOS_SESSION_COOKIE`
- `CHAT_INPUT_SELECTOR`: campo de escritura del chat
- `CHAT_SEND_SELECTOR`: botón para enviar
- `CHAT_MESSAGE_SELECTOR`: selector de cada mensaje individual del chat
- `STREAM_TRANSCRIPT_SELECTOR`: elementos de subtítulos/transcripción del
  streamer dentro de la página autenticada

Los selectores deben obtenerse de la interfaz de Starvios con sesión iniciada.
No uses un selector genérico para la caja o los subtítulos. Si Starvios no
expone subtítulos en la página, el bot no puede saber qué estás diciendo y
omitirá la publicación; en ese caso se necesita una fuente de transcripción de
audio disponible para el workflow.

Al iniciar el workflow, `dry_run` está desactivado por defecto y publica si hay
contexto suficiente. Actívalo para validar que encuentra el campo y escribe el
borrador sin enviarlo. El envío se confirma solo cuando el texto aparece en el
chat. Los artefactos de diagnóstico pueden contener contenido visible del
directo.
