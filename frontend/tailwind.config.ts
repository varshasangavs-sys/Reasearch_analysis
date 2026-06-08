import type { Config } from "tailwindcss";

/**
 * Tailwind theme: a thin layer over the CSS variables defined in globals.css.
 *
 * Why have BOTH CSS vars and Tailwind tokens (not just one):
 *   CSS variables let us swap palettes at runtime (dark mode later).
 *   Tailwind tokens give IDE autocomplete and short class names.
 *   Tailwind values reference the vars — single source of truth.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        rule: "var(--rule)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        "bg-card": "var(--bg-card)",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontSize: {
        body: ["17px", { lineHeight: "1.65" }],
      },
      maxWidth: {
        reading: "68ch",
      },
      letterSpacing: {
        display: "-0.018em",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "soft-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "fade-up": "fade-up 200ms ease-out forwards",
        "soft-pulse": "soft-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
