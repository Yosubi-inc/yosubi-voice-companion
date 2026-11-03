import { expect, test } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

test("frontend source contains no model credential name", () => {
  function visit(dir: string): void {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (["node_modules", ".next", ".git"].includes(entry.name)) continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (/\.(ts|tsx|js|jsx|json|css|md)$/.test(entry.name)) expect(readFileSync(path, "utf8")).not.toContain("MODEL_" + "API_KEY");
    }
  }
  visit(join(process.cwd(), "../frontend"));
});

test("recorded audio and chat reach backend", async ({ page }) => {
  await page.route("**/backend/stt?*", route => route.fulfill({ json: { transcript: "Hello", language: "en" } }));
  let chatBody: any;
  await page.route("**/backend/chat", async route => { chatBody = route.request().postDataJSON(); await route.fulfill({ json: { text: "Backend reply" } }); });
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => ({ getTracks: () => [{ stop() {} }] }) });
    Object.defineProperty(window, "MediaRecorder", { value: class {
      state = "inactive"; ondataavailable: ((event: {data: Blob}) => void) | null = null; onstop: (() => void) | null = null;
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; this.ondataavailable?.({ data: new Blob(["audio"], { type: "audio/webm" }) }); this.onstop?.(); }
    } });
    window.speechSynthesis.speak = () => {};
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Start talking/ }).click();
  await expect(page.getByText("Backend reply")).toBeVisible({ timeout: 10000 });
  expect(chatBody.messages.at(-1)).toEqual({ role: "user", content: "Hello" });
});

test("unreachable backend uses fake response", async ({ page }) => {
  await page.route("**/backend/**", route => route.abort());
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => ({ getTracks: () => [{ stop() {} }] }) });
    Object.defineProperty(window, "MediaRecorder", { value: class { state = "inactive"; start() { this.state = "recording"; } stop() { this.state = "inactive"; } } });
    window.speechSynthesis.speak = () => {};
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Start talking/ }).click();
  await page.getByLabel("Fake transcript").fill("Hello");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("I am listening. How can I help?")).toBeVisible();
});
