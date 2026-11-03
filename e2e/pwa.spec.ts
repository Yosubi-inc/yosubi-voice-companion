import { expect, test } from "@playwright/test";

test("PWA install surface is served", async ({ page }) => {
  const manifest = await page.request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBe(true);
  const body = await manifest.json();
  expect(body.name).toBe("Sparks, your community companion");
  expect(body.short_name).toBe("Sparks");
  expect(body.icons.map((icon: { sizes: string }) => icon.sizes).sort()).toEqual(["192x192", "512x512"]);
  const worker = await page.request.get("/sw.js");
  expect(worker.ok()).toBe(true);
  await page.goto("/");
  await expect(page.locator('link[rel="manifest"]')).toHaveCount(1);
  await expect(page.locator('meta[name="theme-color"]')).toHaveCount(1);
});
