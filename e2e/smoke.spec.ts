import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(["microphone"]);
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => ({ getTracks: () => [{ stop() {} }] }) });
    Object.defineProperty(window, "MediaRecorder", { value: class {
      state = "inactive";
      ondataavailable = null;
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; }
    } });
    const calls: { text: string; lang: string }[] = [];
    Object.assign(window, { speechCalls: calls, cancelCount: 0 });
    window.speechSynthesis.speak = (utterance) => { calls.push({ text: utterance.text, lang: utterance.lang }); };
    window.speechSynthesis.cancel = () => { (window as unknown as { cancelCount: number }).cancelCount++; };
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Start talking/ }).click();
  await expect(page.getByRole("status")).toHaveText("Listening");
});

test("conversation switches both ways and speaks action confirmation", async ({ page }) => {
  await page.getByLabel("Fake transcript").fill("Hello");
  await page.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { speechCalls: { lang: string }[] }).speechCalls.length)).toBe(1);
  await page.getByLabel("Fake transcript").fill("Hola, quiero español");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByLabel("Transcripción simulada")).toBeVisible();
  await page.getByLabel("Transcripción simulada").fill("acción de prueba");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(/Acción de prueba completada/)).toBeVisible();
  await page.getByLabel("Transcripción simulada").fill("English please");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByLabel("Fake transcript")).toBeVisible();
  await page.getByLabel("Fake transcript").fill("demo action");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Demo action completed/)).toBeVisible();
  const calls = await page.evaluate(() => (window as unknown as { speechCalls: { text: string; lang: string }[] }).speechCalls);
  expect(calls.map(call => call.lang)).toEqual(["en-US", "es-ES", "es-ES", "en-US", "en-US"]);
  expect(calls[2].text).toContain("Acción de prueba completada");
  expect(calls[4].text).toContain("Demo action completed");
  await page.getByRole("button", { name: /Stop talking/ }).click();
  await expect(page.getByRole("status")).toHaveText("Stopped");
});

test("new input interrupts speech and is processed", async ({ page }) => {
  await page.getByLabel("Fake transcript").fill("Hello");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("status")).toHaveText("Speaking");
  const before = await page.evaluate(() => (window as unknown as { cancelCount: number }).cancelCount);
  await page.getByLabel("Fake transcript").fill("Hola");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Te escucho/)).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { cancelCount: number }).cancelCount)).toBeGreaterThan(before);
  expect(await page.evaluate(() => (window as unknown as { speechCalls: { lang: string }[] }).speechCalls.at(-1)?.lang)).toBe("es-ES");
});

test("transcript, status and language remain visible", async ({ page }) => {
  await page.getByLabel("Fake transcript").fill("demo action");
  await page.getByRole("button", { name: "Send" }).click();
  const conversation = page.getByRole("region", { name: "Conversation" });
  await expect(conversation.getByText("demo action", { exact: true })).toBeVisible();
  await expect(conversation.getByText("Understood.")).toBeVisible();
  await expect(conversation.getByText(/Demo action completed/)).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Speaking");
  await expect(page.getByLabel("Language")).toHaveText("Language: EN");
  await page.getByLabel("Fake transcript").fill("Hola");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByLabel("Idioma")).toHaveText("Idioma: ES");
});

test("status moves through thinking and back to listening", async ({ page }) => {
  await page.evaluate(() => {
    const status = document.querySelector('[role="status"]')!;
    const changes: string[] = [];
    Object.assign(window, { statusChanges: changes });
    new MutationObserver(records => records.forEach(record => {
      if (record.oldValue) changes.push(record.oldValue);
      changes.push(status.textContent || "");
    })).observe(status, { subtree: true, characterData: true, characterDataOldValue: true, childList: true });
    window.speechSynthesis.speak = utterance => { setTimeout(() => utterance.dispatchEvent(new Event("end")), 100); };
  });
  await page.getByLabel("Fake transcript").fill("Hello");
  await page.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { statusChanges: string[] }).statusChanges)).toContain("Thinking");
  await expect(page.getByRole("status")).toHaveText("Listening");
});
