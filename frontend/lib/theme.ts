export const THEME_STORAGE_KEY = "datapilot-theme";

/**
 * Runs before hydration (inlined into <head> by app/layout.tsx) so there's no flash of the
 * wrong theme. Dark is the product's default identity — only an explicit stored "light" choice,
 * or a system preference with no stored choice yet, opts into `.light`.
 */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("${THEME_STORAGE_KEY}");
    var wantsLight = stored ? stored === "light" : matchMedia("(prefers-color-scheme: light)").matches;
    if (wantsLight) document.documentElement.classList.add("light");
  } catch (e) {}
})();
`;

export type ThemeName = "dark" | "light";

export function getStoredTheme(): ThemeName {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.classList.contains("light") ? "light" : "dark";
}

export function setTheme(theme: ThemeName): void {
  document.documentElement.classList.toggle("light", theme === "light");
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // localStorage unavailable (private browsing, etc.) — theme just won't persist.
  }
}
