import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NotebookPanel } from "@/components/notebook-panel";
import type { NotebookCell } from "@/types";

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
    render(
      <NotebookPanel cells={[cell({ position: 3 })]} onAskAboutCell={onAskAboutCell} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /ask about this cell/i }));
    expect(onAskAboutCell).toHaveBeenCalledWith(3);
  });
});
