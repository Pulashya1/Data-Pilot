import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import { ApiError, requestLoginLink } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, requestLoginLink: vi.fn() };
});

const mockedRequestLoginLink = vi.mocked(requestLoginLink);

describe("LoginPage", () => {
  it("shows the dev-mode login link when SMTP isn't configured", async () => {
    mockedRequestLoginLink.mockResolvedValue({
      detail: "SMTP isn't configured, so here's your dev-mode sign-in link directly.",
      dev_login_url: "http://localhost:3000/auth/verify?token=abc123",
    });
    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "person@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));

    await waitFor(() => {
      expect(screen.getByText(/dev-mode sign-in link/)).toBeTruthy();
    });
    expect(mockedRequestLoginLink).toHaveBeenCalledWith("person@example.com");
    expect(
      screen.getByRole("link", { name: "http://localhost:3000/auth/verify?token=abc123" }),
    ).toBeTruthy();
  });

  it("shows an error message when the request fails", async () => {
    // A well-formed address, so jsdom's built-in `type="email"` constraint validation lets the
    // submit through — this is testing the *backend* rejecting it (e.g. rate limited), not
    // client-side format validation.
    mockedRequestLoginLink.mockRejectedValue(
      new ApiError("Too many requests. Please slow down.", 429),
    );
    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "person@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));

    await waitFor(() => {
      expect(screen.getByText("Too many requests. Please slow down.")).toBeTruthy();
    });
  });
});
