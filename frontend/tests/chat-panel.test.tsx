import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/chat-panel";
import * as api from "@/lib/api";
import type { ChatMessageOut } from "@/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof api>("@/lib/api");
  return {
    ...actual,
    getMessages: vi.fn(),
    askQuestion: vi.fn(),
  };
});

function message(overrides: Partial<ChatMessageOut> = {}): ChatMessageOut {
  return {
    id: "m1",
    session_id: "s1",
    role: "assistant",
    content: "This dataset has 2 columns.",
    referenced_cell_ids: null,
    exploratory_cell_id: null,
    degraded: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.mocked(api.getMessages).mockReset();
    vi.mocked(api.askQuestion).mockReset();
  });

  it("shows a placeholder when there's no history yet", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([]);
    render(<ChatPanel sessionId="s1" />);
    await waitFor(() => expect(api.getMessages).toHaveBeenCalledWith("s1"));
    expect(screen.getByText(/ask about the dataset/i)).toBeTruthy();
  });

  it("loads and renders existing message history", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([
      message({ id: "u1", role: "user", content: "What columns are there?" }),
      message({ id: "a1", role: "assistant", content: "id and age." }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(await screen.findByText("What columns are there?")).toBeTruthy();
    expect(screen.getByText("id and age.")).toBeTruthy();
  });

  it("sends a question and refreshes the history", async () => {
    vi.mocked(api.getMessages)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        message({ id: "u1", role: "user", content: "how many rows?" }),
        message({ id: "a1", role: "assistant", content: "20 rows." }),
      ]);
    vi.mocked(api.askQuestion).mockResolvedValue(message({ content: "20 rows." }));

    render(<ChatPanel sessionId="s1" />);
    await waitFor(() => expect(api.getMessages).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), {
      target: { value: "how many rows?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(api.askQuestion).toHaveBeenCalledWith("s1", "how many rows?"));
    expect(await screen.findByText("20 rows.")).toBeTruthy();
  });

  it("shows a degraded badge when the LLM fell back to a heuristic", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([message({ degraded: true })]);
    render(<ChatPanel sessionId="s1" />);
    expect(await screen.findByText(/answered without the llm/i)).toBeTruthy();
  });

  it("fills the input from a cell-reference prefill", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([]);
    const onPrefillConsumed = vi.fn();
    render(<ChatPanel sessionId="s1" prefill="@cell-3" onPrefillConsumed={onPrefillConsumed} />);
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/ask a question/i) as HTMLInputElement;
      expect(input.value).toBe("@cell-3 ");
    });
    expect(onPrefillConsumed).toHaveBeenCalled();
  });

  it("turns @cell references into buttons that report the cell position", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([
      message({ content: "See @cell-4 for the outliers." }),
    ]);
    const onCellLinkClick = vi.fn();
    render(<ChatPanel sessionId="s1" onCellLinkClick={onCellLinkClick} />);
    fireEvent.click(await screen.findByRole("button", { name: "@cell-4" }));
    expect(onCellLinkClick).toHaveBeenCalledWith(4);
  });

  it("sends a suggested question when clicked", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([]);
    vi.mocked(api.askQuestion).mockResolvedValue(message());
    render(<ChatPanel sessionId="s1" />);
    fireEvent.click(await screen.findByRole("button", { name: /biggest data quality problems/ }));
    await waitFor(() =>
      expect(api.askQuestion).toHaveBeenCalledWith(
        "s1",
        "What are the biggest data quality problems here?",
      ),
    );
  });

  it("keeps the question in the box when sending fails", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([]);
    vi.mocked(api.askQuestion).mockRejectedValue(new api.ApiError("Over budget", 429));
    render(<ChatPanel sessionId="s1" />);
    const box = screen.getByPlaceholderText(/ask a question/i) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "why?" } });
    fireEvent.click(screen.getByRole("button", { name: /^ask$/i }));
    expect(await screen.findByText("Over budget")).toBeTruthy();
    expect(box.value).toBe("why?");
  });

  it("renders markdown tables in answers as tables", async () => {
    vi.mocked(api.getMessages).mockResolvedValue([
      message({ content: ["| Column | VIF |", "|---|---|", "| Age | 1.02 |"].join("\n") }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(await screen.findByRole("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "VIF" })).toBeTruthy();
    expect(screen.getByRole("cell", { name: "1.02" })).toBeTruthy();
  });
});
