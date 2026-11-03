import { expect, test } from "@playwright/test";
import { pickVoice, speakReply, toSpokenText, cancelSpeech } from "../frontend/lib/speak";

const voice = (name: string, lang: string) => ({ name, lang } as SpeechSynthesisVoice);

test("cleans Markdown and picks a natural voice in each language", () => {
  expect(toSpokenText("## Hello **friend**\n- Visit [our site](https://example.invalid)\n2. _Welcome_"))
    .toBe("Hello friend, Visit our site, Welcome");
  expect(toSpokenText("Hello 👋 friend 🎉")).toBe("Hello friend");
  const voices = [voice("Default", "en-US"), voice("Google US English", "en-US"), voice("Google español", "es-ES")];
  expect(pickVoice(voices, "en")?.name).toBe("Google US English");
  expect(pickVoice(voices, "es")?.name).toBe("Google español");
  expect(pickVoice([voice("Microsoft Guy Natural", "en-US"), voice("Microsoft Aria Natural", "en-US")], "en")?.name).toBe("Microsoft Aria Natural");
  expect(pickVoice([], "en")).toBeUndefined();
  expect(pickVoice([voice("Fallback", "es-MX")], "es")?.name).toBe("Fallback");
});

test("waits for voices, queues sentences and resolves on the final event", async () => {
  const calls: SpeechSynthesisUtterance[] = [];
  let voices: SpeechSynthesisVoice[] = [];
  const synth = new EventTarget() as EventTarget & SpeechSynthesis;
  synth.getVoices = () => voices;
  synth.cancel = () => {};
  synth.speak = utterance => { calls.push(utterance); };
  class Utterance extends EventTarget {
    text: string; lang = ""; rate = 1; pitch = 1; voice: SpeechSynthesisVoice | null = null;
    onend: (() => void) | null = null; onerror: (() => void) | null = null;
    constructor(text: string) { super(); this.text = text; }
  }
  const oldWindow = globalThis.window;
  const oldUtterance = globalThis.SpeechSynthesisUtterance;
  Object.assign(globalThis, { window: { speechSynthesis: synth }, SpeechSynthesisUtterance: Utterance });
  try {
    let finished = false;
    const pending = speakReply("**Hello.** How are you?", "en").then(() => { finished = true; });
    expect(calls).toHaveLength(0);
    voices = [voice("Google US English", "en-US")];
    synth.dispatchEvent(new Event("voiceschanged"));
    expect(calls.map(call => call.text)).toEqual(["Hello.", "How are you?"]);
    expect(calls[0].voice?.name).toBe("Google US English");
    expect([calls[0].rate, calls[0].pitch, calls[0].lang]).toEqual([0.95, 1.05, "en-US"]);
    expect(finished).toBe(false);
    calls[1].onend?.call(calls[1], {} as SpeechSynthesisEvent);
    await pending;
    expect(finished).toBe(true);
    voices = [];
    const interrupted = speakReply("No late speech.", "es");
    cancelSpeech();
    synth.dispatchEvent(new Event("voiceschanged"));
    await interrupted;
    expect(calls).toHaveLength(2);
  } finally {
    Object.assign(globalThis, { window: oldWindow, SpeechSynthesisUtterance: oldUtterance });
  }
});
