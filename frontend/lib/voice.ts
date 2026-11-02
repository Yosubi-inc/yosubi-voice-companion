import type { Language } from "./conversation";

// A streaming adapter receives audio chunks and emits endpointed final transcripts.
export interface TranscriptionSession {
  pushAudio(chunk: Blob): void;
  stop(): void;
}
export interface SpeechToText {
  start(onFinal: (text: string) => void): TranscriptionSession;
}
export type ChatMessage = { role: "user" | "assistant"; content: string };
export type AgentReply = { text: string; language: Language; actionConfirmation?: string };
// Messages follow the role/content shape of chat completions.
export interface Agent { complete(messages: ChatMessage[], language: Language): Promise<AgentReply>; }

export class FakeSTT implements SpeechToText {
  private onFinal: ((text: string) => void) | null = null;
  start(onFinal: (text: string) => void): TranscriptionSession {
    this.onFinal = onFinal;
    return { pushAudio: () => {}, stop: () => { this.onFinal = null; } };
  }
  submit(text: string) { this.onFinal?.(text); }
}

export function detectLanguage(text: string, previous: Language): Language {
  const lower = text.toLocaleLowerCase();
  if (/\b(english|inglés|ingles)\b/.test(lower)) return "en";
  if (/\b(spanish|español|espanol)\b/.test(lower)) return "es";
  if (/[¿¡áéíóúñ]|\b(hola|gracias|quiero|puedes|necesito|sí|si|por favor|recordatorio|tarea)\b/.test(lower)) return "es";
  if (/\b(hello|hi|thanks|please|can you|i want|reminder|task|yes)\b/.test(lower)) return "en";
  return previous;
}

export class FakeAgent implements Agent {
  async complete(messages: ChatMessage[], language: Language): Promise<AgentReply> {
    const text = messages[messages.length - 1]?.content ?? "";
    const isAction = /\b(demo action|acción de prueba|accion de prueba)\b/i.test(text);
    if (isAction) return { language, text: language === "es" ? "Entendido." : "Understood.", actionConfirmation: language === "es" ? "Acción de prueba completada. No se cambió nada fuera de esta demostración." : "Demo action completed. Nothing outside this demonstration was changed." };
    return { language, text: language === "es" ? "Te escucho. ¿En qué puedo ayudarte?" : "I am listening. How can I help?" };
  }
}
