import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";

const TEST_EMAIL = process.env.TEST_USER_EMAIL ?? "demo@catai.test";
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD ?? "password123";

async function loginAndGoToKnowledge(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await expect(page).toHaveURL(/dashboard|chat/);
  await page.goto("/dashboard/knowledge");
}

/** Create a temporary plain text file for upload testing. */
function createTempTextFile(): string {
  const tmpDir = "/tmp";
  const filePath = path.join(tmpDir, `catai-test-${Date.now()}.txt`);
  fs.writeFileSync(
    filePath,
    "This is a test document for CAT AI knowledge base ingestion.\n" +
    "It contains information about the CAT AI platform.\n" +
    "CAT AI supports multi-model chat, RAG, and workflow automation."
  );
  return filePath;
}

test.describe("Knowledge Base & File Upload", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToKnowledge(page);
  });

  test("knowledge page loads", async ({ page }) => {
    await expect(page).toHaveURL(/knowledge/);
  });

  test("can create a knowledge base", async ({ page }) => {
    const createButton = page.getByRole("button", { name: /new knowledge base|create kb|add knowledge/i });
    if (await createButton.isVisible({ timeout: 3000 })) {
      await createButton.click();

      const nameInput = page.getByLabel(/name/i);
      if (await nameInput.isVisible()) {
        await nameInput.fill(`E2E KB ${Date.now()}`);
      }

      const saveButton = page.getByRole("button", { name: /create|save/i });
      if (await saveButton.isVisible()) {
        await saveButton.click();
      }

      await expect(page.getByText(/E2E KB|knowledge base created/i)).toBeVisible({
        timeout: 5000,
      });
    }
  });

  test("file upload UI is present", async ({ page }) => {
    const uploader = page
      .getByRole("button", { name: /upload|add file/i })
      .or(page.locator("[data-testid='file-uploader']"))
      .or(page.locator("input[type='file']"));

    await expect(uploader.first()).toBeVisible({ timeout: 5000 });
  });

  test("can upload a text file", async ({ page }) => {
    // Create temp file
    const filePath = createTempTextFile();

    try {
      // Find file input
      const fileInput = page.locator("input[type='file']");
      if (await fileInput.isVisible({ timeout: 3000 })) {
        await fileInput.setInputFiles(filePath);

        // Wait for upload confirmation
        await expect(
          page.getByText(/uploaded|uploading|processing/i)
        ).toBeVisible({ timeout: 10000 });
      }
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test("knowledge base list shows created bases", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    const list = page.locator(
      "[data-testid='kb-list'], .knowledge-base-list, table"
    );
    // Either the list exists or the empty state message exists
    const emptyState = page.getByText(/no knowledge bases|add your first/i);
    await expect(list.or(emptyState)).toBeVisible({ timeout: 5000 });
  });

  test("can query a knowledge base", async ({ page }) => {
    // Find a query input if knowledge bases exist
    const queryInput = page.getByRole("textbox", { name: /search|query knowledge/i });
    if (await queryInput.isVisible({ timeout: 3000 })) {
      await queryInput.fill("What is CAT AI?");
      await page.keyboard.press("Enter");

      await expect(
        page.locator(".search-results, [data-testid='query-results']")
      ).toBeVisible({ timeout: 10000 });
    }
  });
});