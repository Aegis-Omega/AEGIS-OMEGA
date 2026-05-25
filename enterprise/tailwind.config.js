/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        aegis: {
          // Background surfaces
          void:    '#0A0A0C',
          deep:    '#0C0C0E',
          bg:      '#0F0F11',
          surface: '#141416',
          card:    '#1A1A1E',
          hover:   '#1E1E26',
          active:  '#22222C',

          // Borders
          'border-subtle':  '#17171A',
          border:           '#1E1E22',
          'border-medium':  '#27272D',
          'border-strong':  '#3F3F46',

          // Text
          text:      '#ECEAE3',
          secondary: '#A1A1AA',
          muted:     '#6B6B7A',
          disabled:  '#3F3F46',

          // Epistemic tiers
          T0:   '#34D399',  // verified green
          T1:   '#60A5FA',  // trust blue
          T2:   '#A78BFA',  // hypothesis violet
          T3:   '#F59E0B',  // conjecture amber
          T4:   '#F87171',  // blocked red

          // φ golden ratio constant
          phi:       '#C8A96E',
          'phi-glow': '#D4AF7A',
          'phi-deep': '#8B7050',

          // Status
          ok:    '#34D399',
          warn:  '#C8A96E',
          error: '#F87171',
          info:  '#60A5FA',

          // Network verdict
          unified:   '#34D399',
          clustered: '#C8A96E',
          split:     '#F87171',

          // Certification verdicts
          certified:    '#34D399',
          provisional:  '#C8A96E',
          uncertified:  '#F87171',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-t0': 'glow-t0 2s ease-in-out infinite alternate',
      },
      keyframes: {
        'glow-t0': {
          from: { boxShadow: '0 0 4px rgba(52,211,153,0.10)' },
          to:   { boxShadow: '0 0 12px rgba(52,211,153,0.25)' },
        },
      },
    },
  },
  plugins: [],
}
