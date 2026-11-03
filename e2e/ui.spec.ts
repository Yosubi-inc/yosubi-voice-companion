import { expect, test } from "@playwright/test";

for (const width of [360, 1280]) {
  for (const colorScheme of ["light", "dark"] as const) {
    test(`accessible layout at ${width}px in ${colorScheme} mode`, async ({ browser }) => {
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme });
      const page = await context.newPage();
      await page.goto("/");
      const button = page.getByRole("button", { name: "Talk" });
      const box = await button.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(100);
      expect(box!.width).toBeGreaterThanOrEqual(280);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const colors = await page.locator("body").evaluate(element => {
        const style = getComputedStyle(element);
        return { color: style.color, background: style.backgroundColor };
      });
      const luminance = (color: string) => {
        const channels = color.match(/\d+/g)!.slice(0, 3).map(Number).map(value => {
          const c = value / 255;
          return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        });
        return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
      };
      const values = [luminance(colors.color), luminance(colors.background)].sort((a, b) => b - a);
      expect((values[0] + 0.05) / (values[1] + 0.05)).toBeGreaterThanOrEqual(4.5);
      await context.close();
    });
  }
}

test("microphone failure can be retried", async ({ page }) => {
  await page.addInitScript(() => {
    let attempts = 0;
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      if (++attempts === 1) throw new Error("denied");
      return { getTracks: () => [{ stop() {} }] };
    } });
    Object.defineProperty(window, "MediaRecorder", { value: class {
      state = "inactive";
      ondataavailable = null;
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; }
    } });
    Object.defineProperty(window, "WebSocket", { value: class {
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      readyState = 3;
      constructor() { setTimeout(() => { if (this.onerror) this.onerror(); if (this.onclose) this.onclose(); }, 0); }
      addEventListener() {}
      removeEventListener() {}
      send() {}
      close() {}
    } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Talk" }).click();
  await expect(page.getByRole("region", { name: "Voice controls" }).getByRole("alert")).toContainText("microphone");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("region", { name: "Voice controls" }).getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("status")).toHaveText("Listening");
});


