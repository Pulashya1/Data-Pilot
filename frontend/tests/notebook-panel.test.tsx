import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NotebookPanel } from "@/components/notebook-panel";
import type { NotebookCell } from "@/types";

const ESC = String.fromCharCode(27);

function cell(overrides: Partial<NotebookCell>): NotebookCell {
  return {
    id: "c1",
    session_id: "s1",
    position: 0,
    cell_type: "code",
    source: "df.shape",
    label: "Overview",
    outputs: null,
    execution_count: null,
    status: "pending",
    error_message: null,
    is_exploratory: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("NotebookPanel", () => {
  it("shows a placeholder when there are no cells", () => {
    render(<NotebookPanel cells={[]} />);
    expect(screen.getByText(/no notebook cells yet/i)).toBeTruthy();
  });

  it("renders a markdown cell as prose", () => {
    render(<NotebookPanel cells={[cell({ cell_type: "markdown", source: "# Hello\n\nWorld" })]} />);
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByText("World")).toBeTruthy();
  });

  it("renders a code cell with its label, status, and source", () => {
    render(
      <NotebookPanel
        cells={[cell({ label: "Missing values", status: "success", source: "df.isna().sum()" })]}
      />,
    );
    expect(screen.getByText("Missing values")).toBeTruthy();
    expect(screen.getByText("success")).toBeTruthy();
    expect(screen.getByText("df.isna().sum()")).toBeTruthy();
  });

  it("renders a stream output", () => {
    render(
      <NotebookPanel
        cells={[
          cell({
            outputs: [{ output_type: "stream", name: "stdout", text: "(100, 5)" }],
          }),
        ]}
      />,
    );
    expect(screen.getByText("(100, 5)")).toBeTruthy();
  });

  it("renders an error output and the cell's error message", () => {
    render(
      <NotebookPanel
        cells={[
          cell({
            status: "error",
            error_message: "ZeroDivisionError: division by zero",
            outputs: [
              {
                output_type: "error",
                ename: "ZeroDivisionError",
                evalue: "division by zero",
                traceback: ["Traceback...", "ZeroDivisionError: division by zero"],
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("ZeroDivisionError: division by zero")).toBeTruthy();
    expect(screen.getAllByText(/division by zero/).length).toBeGreaterThan(0);
  });

  it("renders a base64 PNG display_data output as an image", () => {
    render(
      <NotebookPanel
        cells={[
          cell({
            outputs: [
              {
                output_type: "display_data",
                data: { "image/png": "aGVsbG8=" },
              },
            ],
          }),
        ]}
      />,
    );
    const img = screen.getByRole("img");
    expect(img.getAttribute("src")).toBe("data:image/png;base64,aGVsbG8=");
  });

  it("badges an exploratory cell", () => {
    render(<NotebookPanel cells={[cell({ is_exploratory: true })]} />);
    expect(screen.getByText("exploratory")).toBeTruthy();
  });

  it("calls onAskAboutCell with the cell's position", () => {
    const onAskAboutCell = vi.fn();
    render(<NotebookPanel cells={[cell({ position: 3 })]} onAskAboutCell={onAskAboutCell} />);
    fireEvent.click(screen.getByRole("button", { name: /ask about this cell/i }));
    expect(onAskAboutCell).toHaveBeenCalledWith(3);
  });

  it("hides code but keeps outputs when Show code is turned off", () => {
    render(
      <NotebookPanel
        cells={[
          cell({
            source: "print(df.shape)",
            outputs: [{ output_type: "stream", name: "stdout", text: "(100, 5)" }],
          }),
        ]}
      />,
    );
    fireEvent.click(screen.getByLabelText("Show code"));
    expect(screen.queryByText("print(df.shape)")).toBeNull();
    expect(screen.getByText("(100, 5)")).toBeTruthy();
  });

  it("asks for confirmation before reverting", () => {
    const onRevert = vi.fn();
    render(<NotebookPanel cells={[cell({ id: "c9" })]} onRevert={onRevert} />);
    fireEvent.click(screen.getByRole("button", { name: /revert to here/i }));
    expect(onRevert).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete them" }));
    expect(onRevert).toHaveBeenCalledWith("c9");
  });

  it("strips terminal color codes from tracebacks", () => {
    render(
      <NotebookPanel
        cells={[
          cell({
            status: "error",
            outputs: [
              {
                output_type: "error",
                ename: "KeyError",
                evalue: "'x'",
                traceback: [`${ESC}[0;31mKeyError${ESC}[0m: 'x'`],
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("KeyError: 'x'")).toBeTruthy();
  });

  it("collapses long code behind a toggle", () => {
    const source = Array.from({ length: 30 }, (_, i) => `x${i} = ${i}`).join("\n");
    render(<NotebookPanel cells={[cell({ source })]} />);
    fireEvent.click(screen.getByRole("button", { name: "Show all 30 lines" }));
    expect(screen.getByRole("button", { name: "Collapse code" })).toBeTruthy();
  });
});
