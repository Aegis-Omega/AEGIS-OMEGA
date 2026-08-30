/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', '../packages/shared/{lib,hooks,components}/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
      },
      colors: {
        cal: {
          bg:      '#080C0A',
          surface: '#0D1410',
          border:  '#162018',
          text:    '#E8F0EB',
          muted:   '#607068',
          accent:  '#22C55E',
          glow:    '#86EFAC',
        },
      },
    },
  },
  plugins: [],
}
