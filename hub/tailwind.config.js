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
          bg:      '#080C0F',
          surface: '#111A1D',
          card:    '#172125',
          border:  '#344044',
          text:    '#EEEAE1',
          muted:   '#A9B6B0',
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
