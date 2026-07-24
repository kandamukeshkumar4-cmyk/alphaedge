import { test, expect } from "@playwright/test";

/**
 * Loop 103 — PWA + SEO launch meta.
 * Asserts manifest link + Open Graph tags in the DOM.
 * Never reads / downloads images (OG image bytes are out of scope).
 */
test.describe("loop103 PWA + SEO meta", () => {
  test("home has manifest link and Open Graph / Twitter tags", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });

    const manifest = page.locator('link[rel="manifest"]');
    await expect(manifest).toHaveCount(1);
    const href = await manifest.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href!).toMatch(/manifest\.webmanifest/i);

    await expect(page.locator('meta[property="og:title"]')).toHaveCount(1);
    await expect(page.locator('meta[property="og:description"]')).toHaveCount(1);
    await expect(page.locator('meta[property="og:type"]')).toHaveCount(1);
    await expect(page.locator('meta[property="og:site_name"]')).toHaveCount(1);
    await expect(page.locator('meta[property="og:url"]')).toHaveCount(1);

    const ogDescription = await page
      .locator('meta[property="og:description"]')
      .getAttribute("content");
    expect(ogDescription?.toLowerCase()).toContain("simulated funds");

    await expect(page.locator('meta[name="twitter:card"]')).toHaveCount(1);
    const twitterCard = await page
      .locator('meta[name="twitter:card"]')
      .getAttribute("content");
    expect(twitterCard).toBe("summary_large_image");

    // Exact disclaimer also shipped as a custom meta for crawlers / audits.
    const disclaimer = page.locator('meta[name="paper-trading-disclaimer"]');
    await expect(disclaimer).toHaveCount(1);
    const disclaimerContent = await disclaimer.getAttribute("content");
    expect(disclaimerContent).toContain("paper-trading simulation");
    expect(disclaimerContent).toContain("simulated funds");
  });
});
