import { describe, expect, it } from "vitest";
import { deriveFlightPath, describeProgress, type FlightPathInput } from "@/lib/flight-path";
import type { DecisionOut } from "@/types";

function decision(kind: DecisionOut["kind"], selected: string | null): DecisionOut {
  return {
    id: kind,
    kind,
    question: "?",
    options: [],
    recommended_option: null,
    selected_option: selected,
    reasoning: null,
    auto_decided: false,
    allow_free_text: false,
    created_at: new Date().toISOString(),
  };
}

function input(overrides: Partial<FlightPathInput> = {}): FlightPathInput {
  return {
    agentStatus: "not_started",
    decisions: [],
    planSteps: [],
    planIndex: 0,
    targetColumn: null,
    templateTitles: {},
    ...overrides,
  };
}

const states = (i: FlightPathInput) => deriveFlightPath(i).map((s) => s.state);

describe("deriveFlightPath", () => {
  it("only has profiling done before the agent runs", () => {
    expect(states(input())).toEqual([
      "done",
      "upcoming",
      "upcoming",
      "upcoming",
      "upcoming",
      "upcoming",
      "upcoming",
    ]);
  });

  it("marks the stage with a pending decision as waiting", () => {
    const i = input({
      agentStatus: "waiting_decision",
      decisions: [decision("target_confirmation", null)],
    });
    expect(states(i).slice(0, 3)).toEqual(["done", "waiting", "upcoming"]);
    expect(describeProgress(i, deriveFlightPath(i))).toMatch(/confirm the target/);
  });

  it("shows exploration progress and names the running analysis", () => {
    const i = input({
      agentStatus: "running",
      decisions: [decision("target_confirmation", "price"), decision("plan_approval", "a,b,c")],
      planSteps: ["a", "b", "c"],
      planIndex: 1,
      templateTitles: { b: "Outliers" },
    });
    const stages = deriveFlightPath(i);
    expect(stages.map((s) => s.state).slice(0, 5)).toEqual([
      "done",
      "done",
      "done",
      "active",
      "upcoming",
    ]);
    expect(stages[1]?.detail).toBe("price");
    expect(stages[3]?.detail).toBe("1 of 3");
    expect(describeProgress(i, stages)).toBe("Running outliers (2 of 3).");
  });

  it("marks a declined baseline as skipped", () => {
    const i = input({
      agentStatus: "running",
      decisions: [
        decision("target_confirmation", "y"),
        decision("plan_approval", "a"),
        decision("feature_engineering_approval", "recommended"),
        decision("baseline_approval", "no"),
      ],
      planSteps: ["a"],
      planIndex: 1,
    });
    expect(states(i)).toEqual(["done", "done", "done", "done", "done", "skipped", "active"]);
  });

  it("skips a baseline the graph never asked about once the run is done", () => {
    const i = input({
      agentStatus: "done",
      decisions: [
        decision("target_confirmation", "(no target)"),
        decision("plan_approval", "a"),
        decision("feature_engineering_approval", "recommended"),
      ],
      planSteps: ["a"],
      planIndex: 1,
    });
    const stages = deriveFlightPath(i);
    expect(stages.map((s) => s.state)).toEqual([
      "done",
      "done",
      "done",
      "done",
      "done",
      "skipped",
      "done",
    ]);
    expect(stages[1]?.detail).toBe("No target");
  });
});
