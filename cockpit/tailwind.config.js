/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        aegis: {
          bg:      '#0C0C0E',
          surface: '#141416',
          border:  '#1E1E22',
          text:    '#ECEAE3',
          muted:   '#6B6B7A',
          accent:  '#60A5FA',
          phi:     '#C8A96E',
          t0:      '#34D399',
          t1:      '#60A5FA',
          t2:      '#A78BFA',
          t3:      '#F59E0B',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
