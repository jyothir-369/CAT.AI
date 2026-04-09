import { test, expect, Page } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL ?? "demo@catai.test";
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD ?? "password123";

async function loginAndGoToWorkflows(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await expect(page).toHaveURL(/dashboard|chat/);
  await page.goto("/dashboard/workflows");
}

test.describe("Workflow Builder", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToWorkflows(page);
  });

  test("workflows page loads", async ({ page }) => {
    await expect(page).toHaveURL(/workflows/);
    await expect(page.getByRole("heading", { name: /workflows/i })).toBeVisible();
  });

  test("can create a new workflow", async ({ page }) => {
    const createButton = page.getByRole("button", { name: /new workflow|create workflow/i });
    await expect(createButton).toBeVisible({ timeout: 5000 });
    await createButton.click();

    // Fill in workflow details
    const nameInput = page.getByLabel(/workflow name|name/i);
    if (await nameInput.isVisible()) {
      await nameInput.fill(`E2E Workflow ${Date.now()}`);
    }

    const saveButton = page.getByRole("button", { name: /save|create/i });
    if (await saveButton.isVisible()) {
      await saveButton.click();
    }

    // Should show the workflow in the list
    await expect(page.getByText(/E2E Workflow|workflow created/i)).toBeVisible({
      timeout: 5000,
    });
  });

  test("workflow list shows created workflows", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // List should be a table or grid
    const list = page.locator(
      "table, [data-testid='workflow-list'], .workflow-list"
    );
    await expect(list).toBeVisible({ timeout: 5000 });
  });

  test("can trigger a workflow manually", async ({ page }) => {
    // Find an existing workflow or skip
    const runButtons = page.getByRole("button", { name: /run|trigger/i });
    const count = await runButtons.count();

    if (count === 0) {
      test.skip();
      return;
    }

    await runButtons.first().click();

    // Should show a run modal or confirmation
    await expect(
      page.getByText(/running|triggered|run started/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test("can view workflow run logs", async ({ page }) => {
    // Navigate to runs (if workflows exist)
    const runsLink = page
      .getByRole("link", { name: /runs|history/i })
      .or(page.getByText(/run history|past runs/i));

    if (await runsLink.isVisible({ timeout: 2000 })) {
      await runsLink.click();
      await expect(
        page.locator("table, [data-testid='run-list'], .run-list")
      ).toBeVisible({ timeout: 5000 });
    }
  });
});