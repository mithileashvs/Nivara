/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#F8F8F3',
        surface: '#FFFFFF',
        forest: {
          DEFAULT: '#173C2B',
          50: '#EEF3F0',
          100: '#D8E3DC',
          200: '#B2C7BC',
          300: '#7FA492',
          400: '#4C7A64',
          500: '#2A5741',
          600: '#173C2B',
          700: '#123022',
          800: '#0D231A',
          900: '#081710',
        },
        sage: {
          DEFAULT: '#AABBA6',
          50: '#F3F6F2',
          100: '#E6EDE4',
          200: '#D2DECF',
          300: '#AABBA6',
          400: '#8CA187',
          500: '#6F8569',
        },
        ink: {
          DEFAULT: '#1B241F',
          muted: '#5C6B61',
          faint: '#8B978F',
        },
        line: '#E4E7DF',
        ok: { DEFAULT: '#3F7D5B', soft: '#E7F1EA' },
        warn: { DEFAULT: '#A4762A', soft: '#F7EEDC' },
        danger: { DEFAULT: '#A8503F', soft: '#F6E6E2' },
        info: { DEFAULT: '#3D6379', soft: '#E6EEF3' },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Newsreader', 'ui-serif', 'Georgia', 'serif'],
      },
      borderRadius: { xl: '0.875rem', '2xl': '1.25rem', '3xl': '1.75rem' },
      boxShadow: {
        card: '0 1px 2px rgba(23,60,43,0.04), 0 8px 24px -16px rgba(23,60,43,0.18)',
        lift: '0 2px 4px rgba(23,60,43,0.05), 0 18px 40px -22px rgba(23,60,43,0.28)',
      },
      keyframes: {
        'fade-in': { from: { opacity: 0 }, to: { opacity: 1 } },
        'rise': { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'none' } },
        'shimmer': { '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        'fade-in': 'fade-in .18s ease-out both',
        'rise': 'rise .22s ease-out both',
      },
    },
  },
  plugins: [],
}
