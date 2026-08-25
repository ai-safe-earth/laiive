import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
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
