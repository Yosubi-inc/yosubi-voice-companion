import { expect, test } from "@playwright/test";

test("realtime session keeps the text form working", async ({ page, context }) => {
  await page.route("**/chat", route => route.abort());
  await context.grantPermissions(["microphone"]);
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => ({ getTracks: () => [{ stop() {} }] }) });
    Object.defineProperty(window, "AudioContext", { value: class {
      sampleRate = 48000;
      audioWorklet = { addModule: async () => {} };
      createMediaStreamSource() { return { connect: () => {} }; }
      createAnalyser() { return { fftSize: 0 }; }
      resume() { return Promise.resolve(); }
      close() { return Promise.resolve(); }
    } });
    Object.defineProperty(window, "AudioWorkletNode", { value: class {
      port = { onmessage: null, postMessage: () => {} };
      constructor() {}
    } });
    Object.defineProperty(window, "WebSocket", { value: class {
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      readyState = 1;
      constructor() { setTimeout(() => this.onmessage && this.onmessage({ data: JSON.stringify({ type: "ready" }) }), 0); }
      addEventListener() {}
      removeEventListener() {}
      send() {}
      close() {}
    } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Talk" }).click();
  await expect(page.getByRole("status")).toHaveText("Listening");
  await page.getByLabel("Type here").fill("Hello");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("region", { name: "Conversation" }).getByText("Hello", { exact: true })).toBeVisible();
});
