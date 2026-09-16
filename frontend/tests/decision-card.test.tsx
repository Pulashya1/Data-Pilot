import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DecisionCard } from "@/components/decision-card";
import type { DecisionOut } from "@/types";

function targetDecision(overrides: Partial<DecisionOut> = {}): DecisionOut {
  return {
    id: "d1",
    kind: "target_confirmation",
    question: "What's the prediction target and problem type?",
    options: ["age", "churned", "(no target)"],
    recommended_option: "churned",
    selected_option: null,
    reasoning: "Column name 'churned' strongly suggests it's the target.",
    auto_decided: false,
    allow_free_text: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("DecisionCard", () => {
  it("shows the question, reasoning, and one button per option", () => {
    render(<DecisionCard decision={targetDecision()} onAnswer={vi.fn()} />);
    expect(
      screen.getByText("What's the prediction target and problem type?"),
    ).toBeTruthy();
    expect(screen.getByText(/strongly suggests/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /churned/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "age" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "(no target)" })).toBeTruthy();
  });

  it("answers with the clicked option for a target_confirmation decision", () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    render(<DecisionCard decision={targetDecision()} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "age" }));
    expect(onAnswer).toHaveBeenCalledWith("d1", "age");
  });

  it("answers with a comma-separated ordered list for a plan_approval decision", () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    const decision = targetDecision({
      kind: "plan_approval",
      question: "Which analysis steps should run, and in what order?",
      options: ["overview", "missing_values", "correlations"],
      recommended_option: "overview,missing_values",
      allow_free_text: true,
    });
    render(<DecisionCard decision={decision} onAnswer={onAnswer} />);

    fireEvent.click(screen.getByRole("button", { name: "Approve plan" }));
    expect(onAnswer).toHaveBeenCalledWith("d1", "overview,missing_values");
  });
});
