import { test, expect } from "@playwright/test";

/**
 * Requires:
 *   backend: MCP_STUB=true uvicorn on :8080
 *   frontend: npm run dev on :5173
 * Install: cd frontend && npm i -D @playwright/test && npx playwright install chromium
 */
test.describe("Trippi-AI happy path", () => {
  test("plans a trip and shows itinerary plus dining", async ({ page }) => {
    await page.goto("http://127.0.0.1:5173/");
    await expect(page.getByText("Trippi-AI")).toBeVisible();
    await page.getByRole("button", { name: /Plan my trip/i }).click();
    await expect(page.getByText(/itinerary/i)).toBeVisible({ timeout: 60000 });
    await expect(page.getByText(/Must try dining/i)).toBeVisible();
    await expect(page.getByText(/Local/i).first()).toBeVisible();
    await expect(page.getByText(/Fancy/i).first()).toBeVisible();
  });
});
