import { expect, test } from "@playwright/test";

test("shows the voice companion shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Yosubi Voice Companion" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start talking" })).toBeDisabled();
});
