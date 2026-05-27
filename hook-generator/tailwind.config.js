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
        hook: {
          bg:      '#0C0A07',
          surface: '#131108',
          border:  '#1F1C0F',
          text:    '#F5F0E8',
          muted:   '#7A7060',
          accent:  '#F59E0B',
          glow:    '#FCD34D',
        },
      },
    },
  },
  plugins: [],
}
