import { test, expect } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL ?? `e2e-${Date.now()}@catai.test`;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD ?? "e2ePassword123!";

test.describe("Authentication", () => {
  test.describe("Registration", () => {
    test("user can register a new account", async ({ page }) => {
      await page.goto("/register");

      await page.getByLabel("Name").fill("E2E Test User");
      await page.getByLabel("Email").fill(`new-${Date.now()}@catai.test`);
      await page.getByLabel("Password").fill("SecurePass123!");
      await page.getByRole("button", { name: /sign up|register/i }).click();

      // Should redirect to dashboard after registration
      await expect(page).toHaveURL(/dashboard|chat/);
    });

    test("shows error on duplicate email", async ({ page }) => {
      await page.goto("/register");

      await page.getByLabel("Name").fill("Duplicate");
      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign up|register/i }).click();

      // Register once
      // Try again with same email
      await page.goto("/register");
      await page.getByLabel("Name").fill("Duplicate");
      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign up|register/i }).click();

      await expect(page.getByText(/already registered|already exists/i)).toBeVisible({
        timeout: 5000,
      });
    });

    test("validates required fields", async ({ page }) => {
      await page.goto("/register");
      await page.getByRole("button", { name: /sign up|register/i }).click();

      // Form should not submit — stays on register page
      await expect(page).toHaveURL(/register/);
    });
  });

  test.describe("Login", () => {
    test("user can log in with valid credentials", async ({ page }) => {
      await page.goto("/login");

      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign in|log in/i }).click();

      await expect(page).toHaveURL(/dashboard|chat/);
    });

    test("shows error on wrong password", async ({ page }) => {
      await page.goto("/login");

      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill("wrongpassword");
      await page.getByRole("button", { name: /sign in|log in/i }).click();

      await expect(
        page.getByText(/invalid credentials|incorrect password|unauthorized/i)
      ).toBeVisible({ timeout: 5000 });
    });

    test("redirects unauthenticated users to login", async ({ page }) => {
      await page.goto("/dashboard/chat");
      await expect(page).toHaveURL(/login/);
    });
  });

  test.describe("Session", () => {
    test("user stays logged in after page refresh", async ({ page }) => {
      // Login
      await page.goto("/login");
      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign in|log in/i }).click();
      await expect(page).toHaveURL(/dashboard|chat/);

      // Reload
      await page.reload();
      await expect(page).toHaveURL(/dashboard|chat/);
    });

    test("logout clears session", async ({ page }) => {
      // Login first
      await page.goto("/login");
      await page.getByLabel("Email").fill(TEST_EMAIL);
      await page.getByLabel("Password").fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign in|log in/i }).click();
      await expect(page).toHaveURL(/dashboard|chat/);

      // Logout
      await page.getByRole("button", { name: /logout|sign out/i }).click();
      await expect(page).toHaveURL(/login|\/$/);

      // Try to access protected route
      await page.goto("/dashboard/chat");
      await expect(page).toHaveURL(/login/);
    });
  });
});