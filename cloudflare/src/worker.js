const PREFIX = "queue/";
const MAX_AUDIO_BYTES = 512 * 1024;
const MAX_AGE_MS = 2 * 60 * 1000;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function tokenIsValid(request, expected) {
  if (!expected) return false;
  const received = request.headers.get("Authorization") || "";
  const wanted = `Bearer ${expected}`;
  let difference = received.length ^ wanted.length;
  const length = Math.max(received.length, wanted.length);
  for (let i = 0; i < length; i++) {
    difference |= (received.charCodeAt(i) || 0) ^ (wanted.charCodeAt(i) || 0);
  }
  return difference === 0;
}

async function pruneExpired(bucket) {
  const cutoff = Date.now() - MAX_AGE_MS;
  let cursor;
  do {
    const page = await bucket.list({ prefix: PREFIX, limit: 1000, cursor });
    const expired = page.objects.filter(
      (object) => Number(object.customMetadata?.uploadedAt || 0) < cutoff,
    );
    if (expired.length) await bucket.delete(expired.map((object) => object.key));
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
}

async function getNextAudio(bucket) {
  const now = Date.now();
  const page = await bucket.list({ prefix: PREFIX, limit: 100 });
  for (const item of page.objects) {
    const uploadedAt = Number(item.customMetadata?.uploadedAt || 0);
    if (!uploadedAt || now - uploadedAt > MAX_AGE_MS) {
      await bucket.delete(item.key);
      continue;
    }
    const object = await bucket.get(item.key);
    if (!object) continue;
    const body = await object.arrayBuffer();
    return new Response(body, {
      headers: {
        "Content-Type": "audio/wav",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "X-Audio-Id": encodeURIComponent(item.key),
        "X-Audio-Timestamp": String(uploadedAt),
      },
    });
  }
  return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}

async function readLimitedBody(request, maxBytes) {
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ ok: true });
    }
    if (!tokenIsValid(request, env.AUDIO_BRIDGE_TOKEN)) {
      return json({ error: "unauthorized" }, 401);
    }
    if (!env.AUDIO_BUCKET) return json({ error: "audio storage unavailable" }, 503);

    if (url.pathname === "/v1/audio" && request.method === "POST") {
      const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim();
      if (contentType !== "audio/wav") return json({ error: "audio/wav required" }, 415);
      const announcedLength = Number(request.headers.get("Content-Length") || 0);
      if (announcedLength > MAX_AUDIO_BYTES) return json({ error: "chunk too large" }, 413);
      const bytes = await readLimitedBody(request, MAX_AUDIO_BYTES);
      if (!bytes || bytes.byteLength < 44) {
        return json({ error: "invalid audio size" }, 413);
      }
      if (
        String.fromCharCode(...bytes.slice(0, 4)) !== "RIFF" ||
        String.fromCharCode(...bytes.slice(8, 12)) !== "WAVE"
      ) return json({ error: "invalid WAV header" }, 415);

      const uploadedAt = Date.now();
      const key = `${PREFIX}${String(uploadedAt).padStart(13, "0")}-${crypto.randomUUID()}.wav`;
      await env.AUDIO_BUCKET.put(key, bytes, {
        httpMetadata: { contentType: "audio/wav" },
        customMetadata: { uploadedAt: String(uploadedAt) },
      });
      return json({ accepted: true }, 201);
    }

    if (url.pathname === "/v1/audio/next" && request.method === "GET") {
      return getNextAudio(env.AUDIO_BUCKET);
    }

    if (url.pathname === "/v1/audio/ack" && request.method === "DELETE") {
      const key = url.searchParams.get("id") || "";
      if (!key.startsWith(PREFIX) || key.length > 200 || key.includes("..")) {
        return json({ error: "invalid audio id" }, 400);
      }
      await env.AUDIO_BUCKET.delete(key);
      return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }

    return json({ error: "not found" }, 404);
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(pruneExpired(env.AUDIO_BUCKET));
  },
};
