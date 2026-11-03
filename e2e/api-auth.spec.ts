import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { apiHeaders } from "../frontend/lib/api";

test("demo authorization header is included only when configured", () => {
  const value = randomUUID();
  expect(apiHeaders(value).get("Authorization")).toBe(`Bearer ${value}`);
  expect(apiHeaders("").has("Authorization")).toBe(false);
});
