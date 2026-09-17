import type { Config } from "tailwindcss";

/**
 * "Control Room" design system (see app/globals.css for the underlying CSS variables). Every
 * color here resolves through a variable so the whole palette flips between the dark default
 * and `.light` in one place — components should reach for these semantic names (`canvas`,
 * `surface`, `ink`, `line`, `accent`...) rather than raw Tailwind grays.
 */
const withOpacity = (variable: string) => `rgb(var(${variable}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: withOpacity("--canvas"),
        surface: withOpacity("--surface"),
        "surface-2": withOpacity("--surface-2"),
        "surface-3": withOpacity("--surface-3"),
        line: {
          DEFAULT: withOpacity("--line"),
          strong: withOpacity("--line-strong"),
        },
        ink: {
          DEFAULT: withOpacity("--ink"),
          secondary: withOpacity("--ink-secondary"),
          tertiary: withOpacity("--ink-tertiary"),
        },
        accent: {
          DEFAULT: withOpacity("--accent"),
          strong: withOpacity("--accent-strong"),
          fg: withOpacity("--accent-fg"),
        },
        secondary: {
          DEFAULT: withOpacity("--secondary"),
          strong: withOpacity("--secondary-strong"),
        },
        info: withOpacity("--info"),
        warning: withOpacity("--warning"),
        critical: withOpacity("--critical"),
        success: withOpacity("--success"),
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "sans-serif"],
        sans: ["var(--font-body)", "ui-sans-serif", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.6rem" }],
        xl: ["1.25rem", { lineHeight: "1.7rem" }],
        "2xl": ["1.5625rem", { lineHeight: "1.9rem" }],
        "3xl": ["2rem", { lineHeight: "2.25rem" }],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "10px",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgb(0 0 0 / 0.2)",
        floating: "0 8px 30px -8px rgb(0 0 0 / 0.45)",
      },
      keyframes: {
        "signal-bar": {
          "0%, 100%": { transform: "scaleY(0.35)" },
          "50%": { transform: "scaleY(1)" },
        },
        "cursor-blink": {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        "signal-bar": "signal-bar 1s ease-in-out infinite",
        "cursor-blink": "cursor-blink 1s step-start infinite",
        "fade-in": "fade-in 0.15s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
