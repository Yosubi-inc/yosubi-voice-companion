import type { Language } from "./conversation";

export function toSpokenText(markdown: string): string {
  return markdown
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*(?:[-+*]|\d+[.)])\s+/gm, ", ")
    .replace(/```[^\n]*\n?|```/g, "")
    .replace(/[*_~`#]/g, "")
    .replace(/\p{Extended_Pictographic}\uFE0F?/gu, "")
    .replace(/[﹋-￯]/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+,/g, ",")
    .replace(/^,\s*/, "")
    .trim();
}

export function ttsBase(): string {
  return (process.env.NEXT_PUBLIC_TTS_URL || "").replace(/\/$/, "");
}

let generation = 0;
let currentAudio: HTMLAudioElement | null = null;

export function cancelSpeech(): void {
  generation++;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
}

function playBlob(blob: Blob, turn: number): Promise<void> {
  return new Promise(resolve => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    const done = () => {
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      resolve();
    };
    audio.onended = done;
    audio.onerror = done;
    if (turn !== generation) { done(); return; }
    audio.play().catch(done);
  });
}

export async function speakReply(text: string, lang: Language | "en-US" | "es-ES"): Promise<void> {
  const turn = ++generation;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  const base = ttsBase();
  if (!base) return;
  const language = lang.startsWith("es") ? "es" : "en";
  const cleaned = toSpokenText(text);
  const chunks = cleaned.match(/[^.!?]+[.!?]+[”"']*|[^.!?]+$/g)?.map(chunk => chunk.trim()).filter(Boolean) ?? [];
  const token = process.env.NEXT_PUBLIC_DEMO_API_TOKEN || "";
  const blobs: Blob[] = [];
  for (const chunk of chunks) {
    if (turn !== generation) return;
    let response: Response;
    try {
      response = await fetch(`${base}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ text: chunk, language }),
      });
    } catch {
      return;
    }
    if (!response.ok || turn !== generation) return;
    blobs.push(await response.blob());
  }
  for (const blob of blobs) {
    if (turn !== generation) return;
    await playBlob(blob, turn);
  }
}
