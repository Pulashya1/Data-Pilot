import { expect, test } from "@playwright/test";

/**
 * MASTER_PROMPT.md §10, §12 Phase 8's one required end-to-end flow: sign in, upload → confirm
 * target → approve plan → answer a decision → download the notebook.
 *
 * `DecisionKind` (backend/app/models/decision.py) only has four members, always reached in this
 * order for a session with a target: `target_confirmation` -> `plan_approval` ->
 * `feature_engineering_approval` -> `baseline_approval`. This test answers the first three and
 * exports right after — feature_engineering_approval is "a decision" per the spec's step list,
 * and the export runs its own throwaway validation kernel (backend/app/api/notebook.py), so it
 * doesn't need to wait for baseline/summarize to finish first.
 */

function sampleCsv(rows = 40): string {
  const lines = ["id,feature_a,feature_b,category,target"];
  for (let i = 0; i < rows; i++) {
    const featureA = (10 + i * 0.37).toFixed(2);
    const featureB = (i % 7 === 0 ? 0.9 : 0.3 + (i % 5) * 0.1).toFixed(2);
    const category = ["A", "B", "C"][i % 3];
    const target = i % 3 === 0 ? 1 : 0;
    lines.push(`${i + 1},${featureA},${featureB},${category},${target}`);
  }
  return lines.join("\n");
}

test("upload -> confirm target -> approve plan -> answer a decision -> download notebook", async ({
  page,
}) => {
  const email = `e2e-${Date.now()}@example.com`;

  // 1. Sign in via the dev-mode magic link (no SMTP configured for local/e2e runs).
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByRole("button", { name: "Send sign-in link" }).click();

  const magicLink = page.getByRole("link", { name: /\/auth\/verify\?token=/ });
  await expect(magicLink).toBeVisible();
  const href = await magicLink.getAttribute("href");
  if (!href) throw new Error("Dev-mode login link had no href.");
  await page.goto(href);
  await expect(page).toHaveURL(/\/sessions$/);

  // 2. Upload a dataset.
  await page.goto("/");
  await page.setInputFiles('input[type="file"]', {
    name: "e2e-dataset.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(sampleCsv()),
  });
  await expect(page).toHaveURL(/\/sessions\/[\w-]+$/, { timeout: 30_000 });

  // 3. Start the agent.
  await page.getByRole("button", { name: "Run agent" }).click();

  // 4. Confirm the target ("target" is name-hinted and 2-valued, so the mock/heuristic
  // recommends it — MASTER_PROMPT.md §5.8, backend/app/agent/heuristics.py).
  await expect(page.getByText("What's the prediction target and problem type?")).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("button", { name: /^target/ }).click();

  // 5. Approve the plan (recommended steps are pre-checked by PlanApprovalCard).
  await expect(page.getByText("Which analysis steps should run")).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Approve plan" }).click();

  // 6. Answer the feature-engineering decision — its only option is "recommended".
  await expect(page.getByText("Build a preprocessing pipeline")).toBeVisible({
    timeout: 120_000,
  });
  await page.getByRole("button", { name: /^recommended/ }).click();

  // 7. Download the exported notebook.
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Export notebook" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
});
