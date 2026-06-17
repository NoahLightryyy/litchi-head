/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* ── 暗色主题（Bloomberg × TradingView 风格） ── */
        bg: {
          primary: "#0D1117",
          secondary: "#161B22",
          tertiary: "#21262D",
          elevated: "#2D333B",
        },
        text: {
          primary: "#E6EDF3",
          secondary: "#8B949E",
          muted: "#484F58",
        },
        accent: {
          blue: "#2962FF",
          green: "#00C853",
          red: "#FF5252",
          gold: "#FFB300",
          purple: "#7C3AED",
        },
        chart: {
          bull: "#26A69A",
          bear: "#EF5350",
          grid: "#1E2A3A",
          volume: "rgba(41, 98, 255, 0.2)",
        },
      },
      fontFamily: {
        number: ["JetBrains Mono", "Cascadia Code", "monospace"],
        body: ["Inter", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
