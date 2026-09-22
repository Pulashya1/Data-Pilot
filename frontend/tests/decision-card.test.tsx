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
    expect(screen.getByText("What's the prediction target and problem type?")).toBeTruthy();
    expect(screen.getByText(/strongly suggests/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /churned/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "age" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /no target/i })).toBeTruthy();
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

  it("shows readable template titles in the plan when provided", () => {
    const decision = targetDecision({
      kind: "plan_approval",
      options: ["overview", "correlations"],
      recommended_option: "overview",
    });
    render(
      <DecisionCard
        decision={decision}
        onAnswer={vi.fn()}
        templates={{
          overview: { key: "overview", title: "Dataset overview", description: "Shape and types" },
        }}
      />,
    );
    expect(screen.getByText("Dataset overview")).toBeTruthy();
    expect(screen.getByText("Shape and types")).toBeTruthy();
  });

  it("answers 'recommended' for feature engineering by default", () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    const decision = targetDecision({
      kind: "feature_engineering_approval",
      question: "Build a preprocessing pipeline with the recommended defaults?",
      options: ["recommended"],
      recommended_option: "recommended",
    });
    render(<DecisionCard decision={decision} onAnswer={onAnswer} columns={["age"]} />);
    fireEvent.click(screen.getByRole("button", { name: "Use recommended settings" }));
    expect(onAnswer).toHaveBeenCalledWith("d1", "recommended");
  });

  it("sends only changed feature-engineering settings as a JSON override", () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    const decision = targetDecision({
      kind: "feature_engineering_approval",
      options: ["recommended"],
      recommended_option: "recommended",
    });
    render(<DecisionCard decision={decision} onAnswer={onAnswer} columns={["age", "zip"]} />);
    fireEvent.click(screen.getByRole("button", { name: /customize/i }));
    fireEvent.change(screen.getByLabelText("Scale numeric features"), {
      target: { value: "none" },
    });
    fireEvent.click(screen.getByRole("button", { name: "zip" }));
    fireEvent.click(screen.getByRole("button", { name: "Build with these settings" }));
    expect(onAnswer).toHaveBeenCalledWith(
      "d1",
      JSON.stringify({ scaling: "none", drop_columns: ["zip"] }),
    );
  });

  it("maps baseline buttons to yes/no answers", () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    const decision = targetDecision({
      kind: "baseline_approval",
      options: ["yes", "no"],
      recommended_option: "yes",
    });
    render(<DecisionCard decision={decision} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(onAnswer).toHaveBeenCalledWith("d1", "no");
  });
});
