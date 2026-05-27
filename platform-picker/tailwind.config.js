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
        brand: {
          bg:      '#0A0A0C',
          surface: '#111113',
          border:  '#1C1C20',
          text:    '#F0EEE7',
          muted:   '#6B6B7A',
          accent:  '#7C3AED',
          glow:    '#A78BFA',
        },
      },
    },
  },
  plugins: [],
}
