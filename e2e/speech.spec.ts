import { expect, test } from "@playwright/test";
import { cancelSpeech, speakReply, toSpokenText } from "../frontend/lib/speak";
import { downsampleTo16k, voiceStreamUrl } from "../frontend/lib/realtime";

test("cleans Markdown and emoji for speech", () => {
  expect(toSpokenText("## Hello **friend**\n- Visit [our site](https://example.invalid)\n2. _Welcome_"))
    .toBe("Hello friend, Visit our site, Welcome");
  expect(toSpokenText("Hello 👋 friend 🎉")).toBe("Hello friend");
});

test("downsamples PCM to 16 kHz mono", () => {
  const input = new Float32Array([0, 0.5, 1, 1, 0.5, 0]);
  expect(Array.from(downsampleTo16k(input, 16000))).toEqual([0, 16383, 32767, 32767, 16383, 0]);
  expect(downsampleTo16k(new Float32Array(480), 48000)).toHaveLength(160);
  expect(downsampleTo16k(new Float32Array([2, -2]), 16000)).toEqual(new Int16Array([32767, -32767]));
});

test("builds the voice stream URL from the page origin", () => {
  process.env.NEXT_PUBLIC_DEMO_API_TOKEN = "tok";
  delete process.env.NEXT_PUBLIC_API_BASE;
  expect(voiceStreamUrl("es")).toMatch(/^wss?:\/\/127\.0\.0\.1:8000\/voice\/stream\?token=tok&language=es$/);
  process.env.NEXT_PUBLIC_API_BASE = "https://api.example.invalid/base";
  expect(voiceStreamUrl("en")).toBe("wss://api.example.invalid/voice/stream?token=tok&language=en");
  delete process.env.NEXT_PUBLIC_API_BASE;
  delete process.env.NEXT_PUBLIC_DEMO_API_TOKEN;
});

test("fetches one clip per sentence and plays them in order", async () => {
  process.env.NEXT_PUBLIC_TTS_URL = "https://tts.example.invalid";
  process.env.NEXT_PUBLIC_DEMO_API_TOKEN = "tok";
  const bodies: { text: string; language: string }[] = [];
  const played: string[] = [];
  const oldFetch = globalThis.fetch;
  const oldAudio = (globalThis as unknown as { Audio?: unknown }).Audio;
  const oldURL = globalThis.URL;
  globalThis.fetch = (async (_url: string, init?: { body?: string }) => {
    bodies.push(JSON.parse(init?.body || "{}"));
    return { ok: true, blob: async () => new Blob([`clip-${bodies.length}`]) };
  }) as typeof fetch;
  (globalThis as unknown as { Audio?: unknown }).Audio = class {
    onended: (() => void) | null = null;
    constructor(public src: string) {}
    play() { played.push(this.src); setTimeout(() => this.onended && this.onended(), 0); return Promise.resolve(); }
    pause() {}
  };
  globalThis.URL.createObjectURL = () => `blob:clip-${played.length + 1}`;
  try {
    await speakReply("**Hello.** How are you? 👋", "en");
    expect(bodies).toEqual([
      { text: "Hello.", language: "en" },
      { text: "How are you?", language: "en" },
    ]);
    expect(played).toEqual(["blob:clip-1", "blob:clip-2"]);
    const pending = speakReply("One. Two. Three.", "en");
    cancelSpeech();
    await pending;
    expect(bodies.length).toBeLessThan(5);
  } finally {
    globalThis.fetch = oldFetch;
    (globalThis as unknown as { Audio?: unknown }).Audio = oldAudio;
    globalThis.URL.createObjectURL = oldURL.createObjectURL;
    delete process.env.NEXT_PUBLIC_TTS_URL;
    delete process.env.NEXT_PUBLIC_DEMO_API_TOKEN;
  }
});
