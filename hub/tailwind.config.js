/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        wordmark: '0.22em',
        label:    '0.15em',
      },
      colors: {
        hub: {
          bg:      '#08090C',
          surface: '#0F1117',
          card:    '#141416',
          border:  '#1A1D27',
          text:    '#ECEAE3',
          muted:   '#6B6B7A',
          accent:  '#6366F1',
          glow:    '#818CF8',
        },
        phi: {
          DEFAULT: '#C8A96E',
          glow:    '#D4AF7A',
          deep:    '#8B7050',
          bg:      '#3D3020',
        },
        aegis: {
          T0:    '#34D399',
          T1:    '#60A5FA',
          T2:    '#A78BFA',
          T3:    '#F59E0B',
          T4:    '#F87171',
          ok:    '#34D399',
          warn:  '#C8A96E',
          error: '#F87171',
        },
      },
    },
  },
  plugins: [],
}
