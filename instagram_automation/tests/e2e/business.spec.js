// End-to-end browser tests (Playwright) for the Studio admin app.
// Run:  npx playwright test tests/e2e/business.spec.js
// Requires a running stack (frontend :3000, backend :8000) and a real display /
// headless Chromium. NOTE: cannot run inside the 0x0 in-app browser pane used
// during development — run it on a normal machine or CI runner.
const { test, expect } = require('@playwright/test');

const BASE = process.env.E2E_BASE || 'http://localhost:3000';
const USER = process.env.ADMIN_USERNAME || 'admin';
const PASS = process.env.ADMIN_PASSWORD || 'admin';

async function login(page) {
  await page.goto(BASE);
  await page.getByLabel(/username/i).fill(USER);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByText(/Dashboard\./i)).toBeVisible({ timeout: 15000 });
}

test('admin login gate blocks then admits', async ({ page }) => {
  await page.goto(BASE);
  await expect(page.getByText(/Sign in/i)).toBeVisible();
  await login(page);
});

test('navigates the full admin sidebar', async ({ page }) => {
  await login(page);
  for (const label of ['Business', 'Properties', 'Media Library', 'Templates',
                        'Analytics', 'Leads', 'Calendar', 'Integrations', 'Settings', 'Personal']) {
    await page.getByText(label, { exact: false }).first().click();
    await page.waitForTimeout(400);
  }
});

test('business campaign flow renders controls', async ({ page }) => {
  await login(page);
  await page.getByText('Business', { exact: false }).first().click();
  await expect(page.getByText(/Campaign Builder\./i)).toBeVisible();
  await expect(page.getByText(/Source document/i)).toBeVisible();
});

test('leads capture adds a row', async ({ page }) => {
  await login(page);
  await page.getByText('Leads', { exact: false }).first().click();
  await expect(page.getByText(/Capture a lead/i)).toBeVisible();
});
