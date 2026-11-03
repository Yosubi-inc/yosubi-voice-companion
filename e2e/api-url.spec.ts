import { expect, test } from "@playwright/test";
import { apiUrl, chat, transcribeAudio } from "../frontend/lib/api";

test("API paths use same origin or the configured backend", async () => {
  expect(apiUrl("/chat", "")).toBe("/chat");
  expect(apiUrl("/stt?language=es", "http://127.0.0.1:8000/")).toBe("http://127.0.0.1:8000/stt?language=es");
});

test("chat and transcription use direct API paths", async () => {
  const calls: string[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (input) => {
    calls.push(String(input));
    return new Response(JSON.stringify({ text: "Hello", transcript: "Hola" }));
  };
  try {
    await chat([{ role: "user", content: "Hello" }], "en");
    await transcribeAudio(new Blob(["audio"], { type: "audio/webm" }), "es");
    expect(calls).toEqual(["/chat", "/stt?language=es"]);
  } finally {
    globalThis.fetch = original;
  }
});
