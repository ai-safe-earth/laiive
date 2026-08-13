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
        orange: "hsl(var(--orange))",
        pro: {
          bg: "hsl(var(--pro-bg))",
          elevated: "hsl(var(--pro-bg-elevated))",
          card: "hsl(var(--pro-bg-card))",
          border: "hsl(var(--pro-border))",
          accent: "hsl(var(--pro-accent))",
        },
      },
      backgroundImage: {
        "gradient-vibrant": "var(--gradient-vibrant)",
        "gradient-subtle": "var(--gradient-subtle)",
        "gradient-glow": "var(--gradient-glow)",
      },
      boxShadow: {
        "glow-primary": "var(--glow-primary)",
        "glow-accent": "var(--glow-accent)",
      },
      fontFamily: {
        montserrat: ["Montserrat", "sans-serif"],
        "ibm-plex": ["IBM Plex Sans", "sans-serif"],
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
