/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        meridian: {
          bg: "#F3F1E9",           // Warm ivory app background (70%)
          surface: "#FAF9F4",      // Lighter tint for panels, cards, and table rows
          surfaceDeep: "#E9E6DA",  // Deeper tint for secondary zones, hover states, table headers
          ink: "#171A19",          // Graphite for headings, body text, key numbers (20%)
          ink2: "#202522",         // Deep charcoal for secondary text, icons, borders on emphasis
          muted: "#898F87",        // Muted grey for labels, metadata, disabled states
          line: "rgba(23, 26, 25, 0.14)", // Standard 1px separator
          lineStrong: "rgba(23, 26, 25, 0.85)", // Strong editorial section rules
          lime: "#C5F36B",         // Acid lime accent (fills only on light; text on dark)
          orange: "#E4774D",       // Burnt orange for extensions, warnings, forced close
          instrument: "#171A19",   // Dark spotlight instrument panels (Graphite)
          
          // Color aliases mapped to new light-first tokens
          graphite: "#171A19",
          charcoal: "#202522",
          panel: "#FAF9F4",
          ivory: "#F3F1E9",
          ivoryLight: "#FAF9F4",
          ivoryDeep: "#E9E6DA",
          grey: "#898F87",
          border: "rgba(23, 26, 25, 0.14)",
          borderLight: "rgba(23, 26, 25, 0.08)",
        },
      },
      fontFamily: {
        heading: ["'Space Grotesk'", "sans-serif"],
        sans: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      borderRadius: {
        none: "0px",
        sm: "2px",
      },
      boxShadow: {
        soft: "0 4px 16px rgba(23, 26, 25, 0.06)",
        float: "0 8px 24px rgba(23, 26, 25, 0.08)",
      },
    },
  },
  plugins: [],
}
