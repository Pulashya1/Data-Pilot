"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { getStoredTheme, setTheme, type ThemeName } from "@/lib/theme";

export function ThemeToggle() {
  const [theme, setThemeState] = useState<ThemeName | null>(null);

  useEffect(() => {
    setThemeState(getStoredTheme());
  }, []);

  if (theme === null) {
    // Avoids a hydration mismatch: the server render doesn't know the client's stored/system
    // preference (that's exactly what the inline script in app/layout.tsx resolves).
    return <div className="h-7 w-7" aria-hidden="true" />;
  }

  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={() => {
        setTheme(next);
        setThemeState(next);
      }}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className="flex h-7 w-7 items-center justify-center rounded-md text-ink-tertiary transition-colors hover:bg-surface-3 hover:text-ink"
    >
      {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
