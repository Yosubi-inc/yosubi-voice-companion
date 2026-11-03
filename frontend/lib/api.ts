export function apiHeaders(token = process.env.NEXT_PUBLIC_DEMO_API_TOKEN): Headers {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export function apiUrl(path: string, base = process.env.NEXT_PUBLIC_API_BASE || ""): string {
  return `${base.replace(/\/$/, "")}${path}`;
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const authorization = apiHeaders().get("Authorization");
  if (authorization) headers.set("Authorization", authorization);
  return fetch(typeof input === "string" && input.startsWith("/") ? apiUrl(input) : input, { ...init, headers });
}


const offline = process.env.NEXT_PUBLIC_DEMO_OFFLINE === "1";
export async function transcribeAudio(audio: Blob, language: "en" | "es"): Promise<string> {
  if (offline) throw new TypeError("offline");
  const response = await apiFetch(`/stt?language=${language}`, { method: "POST", headers: { "Content-Type": audio.type.split(";")[0] || "audio/webm" }, body: audio });
  if (!response.ok) throw new TypeError("transcription unavailable");
  const data = await response.json();
  if (typeof data.transcript !== "string") throw new Error("Invalid transcript");
  return data.transcript;
}
export async function chat(messages: { role: string; content: string }[], language: "en" | "es"): Promise<string> {
  if (offline) throw new TypeError("offline");
  const response = await apiFetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages, language }) });
  if ([404, 500, 502, 503, 504].includes(response.status)) throw new TypeError("chat unavailable");
  if (!response.ok) throw new Error("Chat request failed");
  const data = await response.json();
  if (typeof data.text !== "string") throw new Error("Invalid chat response");
  return data.text;
}
