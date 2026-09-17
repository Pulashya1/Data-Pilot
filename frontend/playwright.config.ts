import { defineConfig, devices } from "@playwright/test";

/**
 * MASTER_PROMPT.md §10, §12 Phase 8: "one Playwright end-to-end test using the mock LLM
 * (upload → confirm target → approve plan → answer a decision → download notebook)".
 *
 * Unlike the vitest component tests, this needs the *full* real stack running — Postgres,
 * Redis, MinIO, and a real sandboxed Docker kernel (MASTER_PROMPT.md §2/§3) — not something
 * Playwright's `webServer` option can spin up on its own, so it isn't configured here. Bring up
 * `docker compose up --build` first (see CLAUDE.md), with `LLM_MODEL=mock` for the backend so
 * this never calls a real, paid LLM (MASTER_PROMPT.md §10/§13), then:
 *
 *     npm run test:e2e
 *
 * `PLAYWRIGHT_BASE_URL` overrides the frontend origin if it isn't on the default port.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
