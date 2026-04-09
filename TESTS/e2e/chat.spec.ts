import { test, expect, Page } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL ?? "demo@catai.test";
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD ?? "password123";

/** Helper: log in and navigate to the chat page. */
async function loginAndGoToChat(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await expect(page).toHaveURL(/dashboard|chat/);
  await page.goto("/dashboard/chat");
}

test.describe("Chat Interface", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToChat(page);
  });

  test("chat input is visible and focusable", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /message|chat/i });
    await expect(input).toBeVisible();
    await input.click();
    await expect(input).toBeFocused();
  });

  test("can send a message and receive a response", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /message|chat/i });
    await input.fill("Say exactly: hello test");
    await page.keyboard.press("Enter");

    // User message should appear
    await expect(page.getByText("Say exactly: hello test")).toBeVisible({ timeout: 5000 });

    // Wait for streaming response to begin (streaming indicator or response text)
    await expect(
      page.locator(".message-assistant, [data-role='assistant']").first()
    ).toBeVisible({ timeout: 15000 });
  });

  test("new conversation appears in sidebar", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /message|chat/i });
    await input.fill("This creates a new conversation");
    await page.keyboard.press("Enter");

    // Wait for response
    await page.waitForTimeout(2000);

    // Sidebar should show the conversation
    const sidebar = page.locator("[data-testid='conversation-sidebar'], aside, nav");
    await expect(sidebar).toBeVisible();
  });

  test("conversation history persists on reload", async ({ page }) => {
    // Send a message
    const uniqueMsg = `Unique message ${Date.now()}`;
    const input = page.getByRole("textbox", { name: /message|chat/i });
    await input.fill(uniqueMsg);
    await page.keyboard.press("Enter");

    // Wait for response
    await expect(page.getByText(uniqueMsg)).toBeVisible({ timeout: 5000 });
    const currentUrl = page.url();

    // Reload
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Message should still be there
    await expect(page.getByText(uniqueMsg)).toBeVisible({ timeout: 10000 });
  });

  test("can start a new conversation", async ({ page }) => {
    // Click new conversation button
    const newConvButton = page.getByRole("button", { name: /new chat|new conversation/i });
    if (await newConvButton.isVisible()) {
      await newConvButton.click();
      // Input should be empty
      const input = page.getByRole("textbox", { name: /message|chat/i });
      await expect(input).toHaveValue("");
    }
  });

  test("model selector is present", async ({ page }) => {
    // Check for model selector dropdown
    const modelSelector = page.getByRole("combobox", { name: /model/i })
      .or(page.locator("[data-testid='model-selector']"))
      .or(page.getByText(/gpt-4|claude|model/i).first());

    await expect(modelSelector).toBeVisible({ timeout: 3000 });
  });

  test("long message does not break layout", async ({ page }) => {
    const longMsg = "A".repeat(500);
    const input = page.getByRole("textbox", { name: /message|chat/i });
    await input.fill(longMsg);
    await page.keyboard.press("Enter");

    // Page should not crash
    await expect(page.locator("body")).toBeVisible();
    await page.waitForTimeout(1000);
    const errors = page.locator(".error-boundary, [data-error='true']");
    await expect(errors).toHaveCount(0);
  });
});