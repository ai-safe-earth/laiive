import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // The one type scale, rem so the phone's text-size setting reaches it.
    // Override rather than extend: a stock `text-xs` must not exist to reach
    // for. T-shirt names are load-bearing — tailwind-merge reads any other
    // `text-<word>` as a colour and drops it next to `text-foreground`.
    // Lifted 2026-09-16: the roles below were already right, the numbers were
    // not. Card copy sat at 14-15px against iOS's 17pt and Android's 16sp body
    // defaults, so the primary content read smaller than the OS around it on
    // every phone. Values only — no role moved, so nothing needed re-tagging.
    fontSize: {
      "2xs": "0.75rem",    // 12   mono badges, status pills (pro + admin only)
      xs: "0.84375rem",    // 13.5 mono labels, section rules, the role line
      sm: "0.9375rem",     // 15   secondary copy, card pills, price badge
      md: "1rem",          // 16   buttons, chips, UI copy, toasts, card meta
      base: "1.0625rem",   // 17   every input — iOS zooms the page below 16
      lg: "1.125rem",      // 18   your own messages in the chat
      xl: "1.25rem",       // 20   assistant answers
      "2xl": "1.4375rem",  // 23   section heads, Bebas card titles
      "3xl": "1.625rem",   // 26   page titles, wordmarks
      "4xl": "1.875rem",   // 30   pro watermark
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Chrome surfaces off reference-screens.html. Not accents — grounds.
        "ink-dim": "hsl(var(--ink-dim))",
        hairline: "hsl(var(--hairline))",
        field: {
          DEFAULT: "hsl(var(--field))",
          border: "hsl(var(--field-border))",
        },
        control: "hsl(var(--control))",
        rule: "hsl(var(--rule))",
        pro: {
          bg: "hsl(var(--pro-bg))",
          elevated: "hsl(var(--pro-bg-elevated))",
          card: "hsl(var(--pro-bg-card))",
          border: "hsl(var(--pro-border))",
          control: "hsl(var(--pro-control))",
          fg: "hsl(var(--pro-fg))",
          muted: "hsl(var(--pro-muted))",
          dim: "hsl(var(--pro-dim))",
          accent: "hsl(var(--pro-accent))",
        },
        mark: {
          verified: "hsl(var(--mark-verified))",
          unverified: "hsl(var(--mark-unverified))",
        },
        status: {
          review: "hsl(var(--status-review))",
          published: "hsl(var(--status-published))",
          attention: "hsl(var(--status-attention))",
          rejected: "hsl(var(--status-rejected))",
          draft: "hsl(var(--status-draft))",
        },
      },
      fontFamily: {
        bebas: ["Bebas Neue", "sans-serif"],
        sans: ["DM Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
} satisfies Config;
