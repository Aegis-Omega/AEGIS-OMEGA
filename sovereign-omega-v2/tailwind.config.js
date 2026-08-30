/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        omega: {
          bg:      '#030A06',
          surface: '#0A1A0E',
          border:  '#1A3A22',
          text:    '#D1FAE5',
          muted:   '#6EE7B7',
          glow:    '#34D399',
          accent:  '#10B981',
          alert:   '#EF4444',
          warn:    '#F59E0B',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
