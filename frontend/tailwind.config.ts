import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // The one type scale, rem so the phone's text-size setting reaches it.
    // Override rather than extend: a stock `text-xs` must not exist to reach
    // for. T-shirt names are load-bearing — tailwind-merge reads any other
    // `text-<word>` as a colour and drops it next to `text-foreground`.
    // Sized on the device, 2026-09-16. Two rounds of guessing at this from a
    // monitor both undershot; the owner read a ladder of specimens on the
    // phone that was failing (411px layout, 16px root, no zoom — so nothing
    // was scaling the page) and put card meta at 20px against the 16px it had.
    //
    // Still one scale, but no longer one size: every value is multiplied by
    // `--type-scale`, which is 1 on the consumer app and .9 on the promoter
    // and admin surfaces (`.surface-pro` in index.css), landing their body
    // copy on 18 against the consumer's 20. The px comments below are the
    // consumer numbers. Geometry tied to the type moved with it — Composer's
    // field, Button's icon size, Avatar — and so did the lockup, which is
    // sized in px and follows nothing on its own.
    fontSize: {
      "2xs": "calc(0.9375rem * var(--type-scale, 1))",  // 15  badges, pills
      xs: "calc(1.0625rem * var(--type-scale, 1))",     // 17  mono labels, rules
      sm: "calc(1.1875rem * var(--type-scale, 1))",     // 19  card pills, price
      md: "calc(1.25rem * var(--type-scale, 1))",       // 20  UI copy, card meta
      base: "calc(1.25rem * var(--type-scale, 1))",     // 20  every input
      lg: "calc(1.375rem * var(--type-scale, 1))",      // 22  your own messages
      xl: "calc(1.5625rem * var(--type-scale, 1))",     // 25  answers
      "2xl": "calc(1.8125rem * var(--type-scale, 1))",  // 29  heads, card titles
      "3xl": "calc(2rem * var(--type-scale, 1))",       // 32  page titles
      "4xl": "calc(2.3125rem * var(--type-scale, 1))",  // 37  pro watermark
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
