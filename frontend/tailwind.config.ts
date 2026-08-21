import type { Config } from "tailwindcss";
import tailwindAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* 颜色由 globals.css 统一控制，避免主题值分叉。 */
        bg: {
          primary: "var(--bg-primary)",
          secondary: "var(--bg-secondary)",
          tertiary: "var(--bg-tertiary)",
          elevated: "var(--bg-elevated)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        accent: {
          blue: "var(--accent-blue)",
          green: "var(--accent-green)",
          red: "var(--accent-red)",
          gold: "var(--accent-gold)",
          purple: "var(--accent-purple)",
        },
        chart: {
          bull: "var(--chart-bull)",
          bear: "var(--chart-bear)",
          grid: "var(--chart-grid)",
          volume: "var(--chart-volume)",
        },
      },
      fontFamily: {
        number: ["JetBrains Mono", "Cascadia Code", "monospace"],
        body: ["Inter", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [tailwindAnimate],
};

export default config;
