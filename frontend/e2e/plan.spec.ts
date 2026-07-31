import { expect, test } from "@playwright/test";

/**
 * Requires:
 *   backend: MCP_STUB=true uvicorn on :8080
 *   frontend: npm run dev on :5173 (started automatically by playwright.config.ts)
 * Browser install: npx playwright install chromium
 */

test.describe("Trippi-AI happy path", () => {
  test("plans a trip and shows itinerary plus dining", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Trippi-AI")).toBeVisible();
    await page.getByRole("button", { name: /Plan my trip/i }).click();

    await expect(page.getByRole("heading", { name: /itinerary/i })).toBeVisible({ timeout: 60000 });
    await expect(page.getByText(/Must try dining/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Local" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fancy" })).toBeVisible();
  });

  test("shows agent chips for every stage", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Plan my trip/i }).click();
    await expect(page.getByRole("heading", { name: /itinerary/i })).toBeVisible({ timeout: 60000 });

    for (const agent of ["Planner", "Research", "Weather", "Packager", "Dining", "Validator"]) {
      await expect(page.getByText(new RegExp(agent, "i")).first()).toBeVisible();
    }
  });

  test("does not overflow horizontally at mobile width", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflows).toBe(false);
  });
});

test.describe("Integrity", () => {
  test("reports an unsourced city instead of inventing places", async ({ page }) => {
    await page.goto("/");

    const city = page.getByLabel("City");
    await city.fill("Reykjavik");
    await page.getByRole("button", { name: /Plan my trip/i }).click();

    await expect(page.getByText(/No real places could be sourced/i)).toBeVisible({ timeout: 60000 });

    // The old fabrication produced names built from the city string.
    await expect(page.getByText(/Reykjavik Old Town Walk/i)).toHaveCount(0);
    await expect(page.getByText(/Reykjavik Local Kitchen/i)).toHaveCount(0);
    await expect(page.getByText(/Reykjavik City Museum/i)).toHaveCount(0);
  });
});
