import type { Language } from "./conversation";

export function toSpokenText(markdown: string): string {
  return markdown
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*(?:[-+*]|\d+[.)])\s+/gm, ", ")
    .replace(/```[^\n]*\n?|```/g, "")
    .replace(/[*_~`#]/g, "")
    .replace(/\p{Extended_Pictographic}\uFE0F?/gu, "")
    .replace(/[\uFE0F\u200D]/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+,/g, ",")
    .replace(/^,\s*/, "")
    .trim();
}

export function pickVoice(voices: SpeechSynthesisVoice[], lang: Language | "en-US" | "es-ES"): SpeechSynthesisVoice | undefined {
  const target = lang.startsWith("es") ? "es" : "en";
  const matching = voices.filter(voice => voice.lang.toLowerCase().split(/[-_]/)[0] === target);
  const female = target === "es"
    ? /paulina|sabina|google espa[ñn]ol|microsoft.*(aria|jenny).*natural|femenina|female/i
    : /aria|jenny|samantha|zira|google us english|female/i;
  const natural = /microsoft.*natural|siri|natural|neural/i;
  return matching.find(voice => female.test(voice.name))
    ?? matching.find(voice => natural.test(voice.name))
    ?? matching.find(voice => voice.lang.toLowerCase() === (target === "es" ? "es-es" : "en-us"))
    ?? matching[0];
}

let currentCancel: (() => void) | undefined;

export function cancelSpeech(): void {
  currentCancel?.();
  window.speechSynthesis.cancel();
}

export function speakReply(text: string, lang: Language | "en-US" | "es-ES"): Promise<void> {
  cancelSpeech();
  const cleaned = toSpokenText(text);
  const chunks = cleaned.match(/[^.!?]+[.!?]+[”"']*|[^.!?]+$/g)?.map(chunk => chunk.trim()).filter(Boolean) ?? [];
  if (!chunks.length) return Promise.resolve();
  return new Promise(resolve => {
    const synth = window.speechSynthesis;
    let done = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = () => {
      if (done) return;
      done = true;
      if (timer) clearTimeout(timer);
      synth.removeEventListener("voiceschanged", start);
      if (currentCancel === finish) currentCancel = undefined;
      resolve();
    };
    const start = () => {
      if (done) return;
      if (timer) clearTimeout(timer);
      synth.removeEventListener("voiceschanged", start);
      const voice = pickVoice(synth.getVoices(), lang);
      chunks.forEach((chunk, index) => {
        const utterance = new SpeechSynthesisUtterance(chunk);
        utterance.lang = lang.startsWith("es") ? "es-ES" : "en-US";
        utterance.rate = 0.95;
        utterance.pitch = 1.05;
        if (voice) utterance.voice = voice;
        if (index === chunks.length - 1) utterance.onend = utterance.onerror = finish;
        synth.speak(utterance);
      });
    };
    currentCancel = finish;
    if (synth.getVoices().length) start();
    else {
      synth.addEventListener("voiceschanged", start);
      timer = setTimeout(start, 250);
    }
  });
}

