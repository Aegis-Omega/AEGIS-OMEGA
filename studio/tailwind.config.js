/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        aegis: {
          void:    '#0A0A0C', deep:    '#0C0C0E', bg:      '#0F0F11',
          surface: '#141416', card:    '#1A1A1E', hover:   '#1E1E26', active: '#22222C',
          'border-subtle': '#17171A', border: '#1E1E22',
          'border-medium': '#27272D', 'border-strong': '#3F3F46',
          text: '#ECEAE3', secondary: '#A1A1AA', muted: '#6B6B7A', disabled: '#3F3F46',
          T0: '#34D399', T1: '#60A5FA', T2: '#A78BFA', T3: '#F59E0B', T4: '#F87171',
          phi: '#C8A96E', 'phi-glow': '#D4AF7A', 'phi-deep': '#8B7050', 'phi-bg': '#3D3020',
          ok: '#34D399', warn: '#C8A96E', error: '#F87171', info: '#60A5FA',
          unified: '#34D399', clustered: '#C8A96E', split: '#F87171',
          certified: '#34D399', provisional: '#C8A96E', uncertified: '#F87171',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: { '2xs': ['0.625rem', { lineHeight: '0.875rem' }] },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
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
